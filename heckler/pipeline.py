"""Pipeline orchestration: threaded capture → transcribe → react → TTS + JSONL logging."""

from __future__ import annotations

import argparse
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import sounddevice as sd

from heckler.audio_capture import AudioCapture, _put_drop_oldest
from heckler.config import HecklerConfig, load_config
from heckler.context_buffer import ContextBuffer
from heckler.logger import HecklerLogger
from heckler.models import DiscardReason, HeckleEvent, Utterance
from heckler.pacing_gate import PacingGate
from heckler.reactor import Reactor
from heckler.semantic_gate import passes_gate
from heckler.speaker import Speaker, SpeakerError
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
        except Exception:
            logger.exception("transcription worker dropped an item after unexpected error")


def _run_reaction_worker(
    *,
    context_buffer: ContextBuffer,
    reactor: Reactor,
    pacing_gate: PacingGate,
    speaker: Speaker,
    heckler_logger: HecklerLogger,
    reaction_queue: queue.Queue,
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
    args = parser.parse_args(argv)

    if args.list_devices:
        print(sd.query_devices())
        return

    logging.basicConfig(level=logging.INFO)

    config = load_config()
    heckler_logger = HecklerLogger(config)

    t0 = time.perf_counter()
    print(
        f"[HECKLER] Loading transcription model ({config.whisper_model_size} / CUDA)...",
        flush=True,
    )
    transcriber = Transcriber(config)
    print(f"[HECKLER] Transcription ready. ({time.perf_counter() - t0:.1f}s)", flush=True)

    t1 = time.perf_counter()
    print(
        f"[HECKLER] Loading TTS model (Kokoro / {config.kokoro_voice})...",
        flush=True,
    )
    speaker = Speaker(config)
    print(f"[HECKLER] TTS ready. ({time.perf_counter() - t1:.1f}s)", flush=True)

    reactor = Reactor(config)

    context_buffer = ContextBuffer(config.context_window_size)
    pacing_gate = PacingGate(config)

    audio_queue: queue.Queue = queue.Queue(maxsize=config.queue_maxsize)
    reaction_queue: queue.Queue = queue.Queue(maxsize=config.queue_maxsize)

    capture = AudioCapture(config, audio_queue, speaker.is_playing)

    transcription_thread = threading.Thread(
        target=_run_transcription_worker,
        kwargs={
            "config": config,
            "audio_queue": audio_queue,
            "reaction_queue": reaction_queue,
            "transcriber": transcriber,
            "heckler_logger": heckler_logger,
        },
        name="heckler-transcription",
        daemon=False,
    )
    reaction_thread = threading.Thread(
        target=_run_reaction_worker,
        kwargs={
            "context_buffer": context_buffer,
            "reactor": reactor,
            "pacing_gate": pacing_gate,
            "speaker": speaker,
            "heckler_logger": heckler_logger,
            "reaction_queue": reaction_queue,
        },
        name="heckler-reaction",
        daemon=False,
    )

    transcription_thread.start()
    reaction_thread.start()

    try:
        capture.start()
        print("[HECKLER] Mic open. Listening.", flush=True)
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
    finally:
        capture.stop()
        _put_shutdown_sentinel(audio_queue)
        transcription_thread.join(timeout=120.0)
        _put_shutdown_sentinel(reaction_queue)
        reaction_thread.join(timeout=120.0)


if __name__ == "__main__":
    main()
