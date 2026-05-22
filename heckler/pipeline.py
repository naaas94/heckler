"""Pipeline orchestration: threaded capture → transcribe → react → TTS with SQLite event persistence."""

from __future__ import annotations

import argparse
import logging
import queue
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional

import sounddevice as sd

if TYPE_CHECKING:
    from heckler.controller import ReactorHolder

from heckler.audio_capture import AudioCapture, _put_drop_oldest
from heckler.config import HecklerConfig, load_config
from heckler.context_buffer import ContextBuffer
from heckler.logger import HecklerLogger
from heckler.models import DiscardReason, HeckleEvent, ReactorResult, Utterance
from heckler.pacing_gate import PacingGate
from heckler.persona import PersonaNotFoundError
from heckler.semantic_gate import passes_gate
from heckler.speaker import Speaker, SpeakerError
from heckler.transcript_store import insert_chunk
from heckler.transcriber import Transcriber

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _put_shutdown_sentinel(q: queue.Queue) -> None:
    """Enqueue ``None``; if ``q`` is full, drop oldest until there is room (shutdown path)."""
    _put_drop_oldest(q, None)


def _execute_spoken_reply(pacing_gate: PacingGate, speaker: Speaker, comment: str) -> float:
    """Coupling surface 6: ``record_output`` immediately before ``speaker.speak``."""
    pacing_gate.record_output()
    return speaker.speak(comment)


def _run_transcription_worker(
    *,
    config: HecklerConfig,
    audio_queue: queue.Queue,
    reaction_queue: queue.Queue,
    transcriber: Transcriber,
    heckler_logger: HecklerLogger,
    on_transcript: Optional[Callable[[str], None]] = None,
) -> None:
    while True:
        try:
            item = audio_queue.get()
        except Exception:
            logger.exception("audio_queue.get failed")
            continue
        if item is None:
            break
        try:
            chunk = item
            text = transcriber.transcribe(chunk).strip()
            passes_density, density = passes_gate(text, config)
            utterance_id = str(uuid.uuid4())
            if not passes_density:
                if config.log_density_failures:
                    event = HeckleEvent(
                        utterance_id=utterance_id,
                        timestamp_iso=_now_iso(),
                        transcript=text,
                        semantic_density=density,
                        passed_density_gate=False,
                        reactor_result=None,
                        passed_score_gate=None,
                        passed_pacing_gate=None,
                        spoken=False,
                        discard_reason=DiscardReason.DENSITY_GATE,
                        cooldown_remaining_at_eval=None,
                        llm_latency_ms=None,
                        tts_latency_ms=None,
                    )
                    heckler_logger.log_event(event)
                continue

            utterance = Utterance(
                utterance_id=utterance_id,
                transcript=text,
                semantic_density=density,
                transcribed_at=time.time(),
                audio_chunk=chunk,
            )
            _put_drop_oldest(reaction_queue, utterance)
            if on_transcript is not None:
                try:
                    on_transcript(text)
                except Exception:
                    logger.exception("on_transcript callback raised in transcription worker")
        except Exception:
            logger.exception("transcription worker dropped an item after unexpected error")


def _run_transcribe_worker(
    *,
    config: HecklerConfig,
    audio_queue: queue.Queue,
    transcriber: Transcriber,
    transcript_conn: sqlite3.Connection,
    session_id: str,
    transcript_lock: threading.Lock,
    on_transcript: Optional[Callable[[str], None]] = None,
) -> None:
    sequence_num = 0
    while True:
        try:
            item = audio_queue.get()
        except Exception:
            logger.exception("audio_queue.get failed (transcribe worker)")
            continue
        if item is None:
            break
        try:
            chunk = item
            text = transcriber.transcribe(chunk).strip()
            if not text:
                continue
            sequence_num += 1
            duration_s = float(chunk.audio.shape[0]) / float(config.sample_rate)
            timestamp_iso = _now_iso()
            with transcript_lock:
                insert_chunk(
                    transcript_conn,
                    session_id=session_id,
                    chunk_text=text,
                    timestamp_iso=timestamp_iso,
                    duration_s=duration_s,
                    sequence_num=sequence_num,
                )
            if on_transcript is not None:
                try:
                    on_transcript(text)
                except Exception:
                    logger.exception("on_transcript callback raised in transcribe worker")
            else:
                print(f"[TRANSCRIBE] {text}", flush=True)
            logger.info(
                "transcribe worker persisted chunk",
                extra={"session_id": session_id, "chunk_sequence_num": sequence_num},
            )
        except Exception:
            logger.exception("transcribe worker dropped an item after unexpected error")


def _run_reaction_worker(
    *,
    context_buffer: ContextBuffer,
    reactor_holder: ReactorHolder,
    pacing_gate: PacingGate,
    speaker: Speaker,
    heckler_logger: HecklerLogger,
    reaction_queue: queue.Queue,
    on_reaction: Optional[Callable[[ReactorResult, bool], None]] = None,
) -> None:
    while True:
        try:
            utterance = reaction_queue.get()
        except Exception:
            logger.exception("reaction_queue.get failed")
            continue
        if utterance is None:
            break
        try:
            in_cooldown, cooldown_remaining = pacing_gate.cooldown_status()
            if in_cooldown:
                heckler_logger.log_event(
                    HeckleEvent(
                        utterance_id=utterance.utterance_id,
                        timestamp_iso=_now_iso(),
                        transcript=utterance.transcript,
                        semantic_density=utterance.semantic_density,
                        passed_density_gate=True,
                        reactor_result=None,
                        passed_score_gate=None,
                        passed_pacing_gate=False,
                        spoken=False,
                        discard_reason=DiscardReason.PACING_GATE,
                        cooldown_remaining_at_eval=cooldown_remaining,
                        llm_latency_ms=None,
                        tts_latency_ms=None,
                    )
                )
                context_buffer.push(utterance.transcript)
                continue

            reactor = reactor_holder.get()
            context_block = context_buffer.get_context_block()
            result, llm_latency_ms, discard_reason = reactor.react(
                utterance, context_block
            )

            if result is None:
                if discard_reason is None:
                    logger.error(
                        "reactor.react() returned (None, %s, None) — contract violation; "
                        "falling back to LLM_ERROR",
                        llm_latency_ms,
                    )
                    discard_reason = DiscardReason.LLM_ERROR
                passed_score: Optional[bool]
                if discard_reason == DiscardReason.LLM_ERROR:
                    passed_score = None
                else:
                    passed_score = False
                heckler_logger.log_event(
                    HeckleEvent(
                        utterance_id=utterance.utterance_id,
                        timestamp_iso=_now_iso(),
                        transcript=utterance.transcript,
                        semantic_density=utterance.semantic_density,
                        passed_density_gate=True,
                        reactor_result=None,
                        passed_score_gate=passed_score,
                        passed_pacing_gate=None,
                        spoken=False,
                        discard_reason=discard_reason,
                        cooldown_remaining_at_eval=None,
                        llm_latency_ms=llm_latency_ms,
                        tts_latency_ms=None,
                    )
                )
                context_buffer.push(utterance.transcript)
                continue

            should_speak, cooldown_remaining = pacing_gate.evaluate(result.score)
            if not should_speak:
                heckler_logger.log_event(
                    HeckleEvent(
                        utterance_id=utterance.utterance_id,
                        timestamp_iso=_now_iso(),
                        transcript=utterance.transcript,
                        semantic_density=utterance.semantic_density,
                        passed_density_gate=True,
                        reactor_result=result,
                        passed_score_gate=True,
                        passed_pacing_gate=False,
                        spoken=False,
                        discard_reason=DiscardReason.PACING_GATE,
                        cooldown_remaining_at_eval=cooldown_remaining,
                        llm_latency_ms=llm_latency_ms,
                        tts_latency_ms=None,
                    )
                )
                if on_reaction is not None:
                    try:
                        on_reaction(result, False)
                    except Exception:
                        logger.exception("on_reaction callback raised (pacing gate)")
                context_buffer.push(utterance.transcript)
                continue

            try:
                tts_ms = _execute_spoken_reply(pacing_gate, speaker, result.comment)
            except SpeakerError:
                heckler_logger.log_event(
                    HeckleEvent(
                        utterance_id=utterance.utterance_id,
                        timestamp_iso=_now_iso(),
                        transcript=utterance.transcript,
                        semantic_density=utterance.semantic_density,
                        passed_density_gate=True,
                        reactor_result=result,
                        passed_score_gate=True,
                        passed_pacing_gate=True,
                        spoken=False,
                        discard_reason=DiscardReason.TTS_ERROR,
                        cooldown_remaining_at_eval=None,
                        llm_latency_ms=llm_latency_ms,
                        tts_latency_ms=None,
                    )
                )
                if on_reaction is not None:
                    try:
                        on_reaction(result, False)
                    except Exception:
                        logger.exception("on_reaction callback raised (TTS error)")
                context_buffer.push(utterance.transcript)
                continue

            heckler_logger.log_event(
                HeckleEvent(
                    utterance_id=utterance.utterance_id,
                    timestamp_iso=_now_iso(),
                    transcript=utterance.transcript,
                    semantic_density=utterance.semantic_density,
                    passed_density_gate=True,
                    reactor_result=result,
                    passed_score_gate=True,
                    passed_pacing_gate=True,
                    spoken=True,
                    discard_reason=None,
                    cooldown_remaining_at_eval=None,
                    llm_latency_ms=llm_latency_ms,
                    tts_latency_ms=tts_ms,
                )
            )
            if on_reaction is not None:
                try:
                    on_reaction(result, True)
                except Exception:
                    logger.exception("on_reaction callback raised (spoken)")
            context_buffer.push(utterance.transcript)
        except Exception:
            logger.exception("reaction worker dropped an utterance after unexpected error")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="heckler")
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List audio devices via sounddevice and exit",
    )
    parser.add_argument(
        "--mode",
        choices=["persona", "transcribe"],
        default=None,
        help="Pipeline mode: persona (full loop) or transcribe (capture + Whisper only)",
    )
    parser.add_argument(
        "--session-name",
        default=None,
        help="Label for the transcription session (default: first 8 chars of session id)",
    )
    parser.add_argument(
        "--persona",
        type=str,
        default=None,
        help=(
            "Persona name (maps to prompts/<name>/; default from HECKLER_PERSONA or 'heckler')"
        ),
    )
    args = parser.parse_args(argv)

    if args.list_devices:
        print(sd.query_devices())
        return

    logging.basicConfig(level=logging.INFO)
    config = load_config()
    mode = args.mode if args.mode is not None else config.mode
    persona_name = args.persona or config.persona_name
    session_name = args.session_name or config.session_name

    from heckler.controller import ControllerCallbacks, PipelineController

    callbacks = ControllerCallbacks(
        on_transcript=lambda text: print(f"[TRANSCRIBE] {text}", flush=True),
        on_reaction=lambda result, spoken: (
            print(f"[HECKLER] {result.comment}", flush=True) if spoken else None
        ),
        on_status=lambda msg: print(f"[HECKLER] {msg}", flush=True),
        on_error=lambda err: print(f"[HECKLER] Error: {err}", flush=True),
    )

    controller = PipelineController(config, callbacks)

    try:
        # ensure_heavy_models loads when signature differs; same locale + voice-only change is a no-op.
        controller.ensure_heavy_models(
            persona_name=persona_name if mode == "persona" else None,
            locale_override=None,  # No CLI locale override in v1
            on_progress=lambda msg: print(f"[HECKLER] {msg}", flush=True),
            mode=mode,
        )
    except Exception as exc:
        print(f"[HECKLER] Error loading models: {exc}", flush=True)
        raise SystemExit(1) from exc

    try:
        controller.start(mode, persona_name=persona_name, session_name=session_name)
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
    except PersonaNotFoundError as exc:
        print(f"[HECKLER] Error: {exc}", flush=True)
        raise SystemExit(1) from exc
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
