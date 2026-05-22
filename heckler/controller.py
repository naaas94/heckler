"""PipelineController: reusable pipeline lifecycle manager for GUI and CLI consumers."""

from __future__ import annotations

import dataclasses
import enum
import logging
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from heckler.audio_capture import AudioCapture
from heckler.config import HecklerConfig, apply_resolved_locale
from heckler.context_buffer import ContextBuffer
from heckler.event_store import open_store
from heckler.logger import HecklerLogger
from heckler.models import ReactorResult
from heckler.pacing_gate import PacingGate
from heckler.persona import apply_persona_overrides, load_persona
from heckler.pipeline import (
    _put_shutdown_sentinel,
    _run_reaction_worker,
    _run_transcribe_worker,
    _run_transcription_worker,
)
from heckler.reactor import Reactor
from heckler.speaker import Speaker
from heckler.transcript_store import (
    close_session,
    create_session,
    export_session_markdown,
    init_transcript_schema,
)
from heckler.transcriber import Transcriber

logger = logging.getLogger(__name__)


class PipelineNotRunningError(RuntimeError):
    """Raised when swap_persona or switch_mode is called while the pipeline is not running."""


class PipelineAlreadyRunningError(RuntimeError):
    """Raised when start() is called while the pipeline is already running."""


class SpeechReloadPolicy(str, enum.Enum):
    auto = "auto"
    ask = "ask"
    never = "never"


@dataclass
class ControllerCallbacks:
    on_transcript: Callable[[str], None]
    on_reaction: Callable[[ReactorResult, bool], None]  # (result, was_spoken)
    on_status: Callable[[str], None]
    on_error: Callable[[str], None]


class ReactorHolder:
    """Thread-safe Reactor reference supporting hot-swap between utterances."""

    def __init__(self, reactor: Reactor) -> None:
        self._reactor = reactor
        self._lock = threading.Lock()

    def get(self) -> Reactor:
        with self._lock:
            return self._reactor

    def swap(self, new_reactor: Reactor) -> None:
        with self._lock:
            self._reactor = new_reactor


class PipelineController:
    """Manages pipeline lifecycle (start/stop/mode-switch/persona-swap) for GUI consumers."""

    def __init__(self, config: HecklerConfig, callbacks: ControllerCallbacks) -> None:
        self._config = config
        self._callbacks = callbacks

        # Heavy models — loaded once, shared across mode switches
        self._transcriber: Optional[Transcriber] = None
        self._speaker: Optional[Speaker] = None

        # Runtime state — cleared on stop
        self._running = False
        self._mode: Optional[str] = None
        self._persona_name: Optional[str] = None
        self._reactor_holder: Optional[ReactorHolder] = None

        # Active worker infrastructure
        self._capture: Optional[AudioCapture] = None
        self._audio_queue: Optional[queue.Queue] = None
        self._reaction_queue: Optional[queue.Queue] = None
        self._threads: list[threading.Thread] = []

        # Transcribe-mode session state (closed on stop)
        self._transcript_conn: Optional[sqlite3.Connection] = None
        self._transcript_session_id: Optional[str] = None
        self._transcript_session_label: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_models(
        self,
        on_progress: Optional[Callable[[str], None]] = None,
        *,
        mode: Optional[str] = None,
        persona_name: Optional[str] = None,
        locale_override: Optional[str] = None,
    ) -> None:
        """Load Transcriber; load Speaker unless ``mode="transcribe"``.

        Heavy models use ``target_speech_config`` (persona merge, optional
        ``locale_override``, or base ``apply_resolved_locale``). Call again when
        the speech-stack signature changes — ``swap_persona`` does not rebuild
        Transcriber/Speaker (caller must guarantee unchanged signature).

        Never call during mode switch or persona swap except via
        ``reload_speech_stack_for_persona`` / ``ensure_heavy_models``.
        """
        model_cfg = self.target_speech_config(
            persona_name=persona_name, locale_override=locale_override
        )

        def _prog(msg: str) -> None:
            if on_progress is not None:
                on_progress(msg)

        _prog(
            f"Loading transcription model ({model_cfg.whisper_model_size} / CUDA)..."
        )
        t0 = time.perf_counter()
        self._transcriber = Transcriber(model_cfg)
        _prog(f"Transcription ready. ({time.perf_counter() - t0:.1f}s)")

        if mode != "transcribe":
            _prog(f"Loading TTS model (Kokoro / {model_cfg.kokoro_voice})...")
            t1 = time.perf_counter()
            self._speaker = Speaker(model_cfg)
            _prog(f"TTS ready. ({time.perf_counter() - t1:.1f}s)")

        logger.info(
            "Speech stack loaded for %r (%s/%s)",
            persona_name,
            model_cfg.whisper_language,
            model_cfg.kokoro_lang_code,
        )

    def loaded_speech_stack(self) -> tuple[str, str] | None:
        if self._transcriber is None:
            return None
        from heckler.locale import speech_stack_signature

        return speech_stack_signature(self._transcriber._config)

    def target_speech_config(
        self,
        *,
        persona_name: Optional[str],
        locale_override: Optional[str] = None,
    ) -> HecklerConfig:
        base = self._config
        if persona_name:
            prompts_root = Path(__file__).resolve().parent.parent / "prompts"
            persona = load_persona(prompts_root / persona_name)
            cfg = apply_persona_overrides(base, persona)
        else:
            cfg = apply_resolved_locale(base)
        if locale_override:
            cfg = apply_resolved_locale(dataclasses.replace(cfg, locale=locale_override))
        return cfg

    def heavy_models_need_reload(
        self,
        *,
        persona_name: Optional[str],
        locale_override: Optional[str] = None,
    ) -> bool:
        from heckler.locale import speech_stack_signature

        target = self.target_speech_config(
            persona_name=persona_name, locale_override=locale_override
        )
        loaded = self.loaded_speech_stack()
        return loaded is None or speech_stack_signature(target) != loaded

    def ensure_heavy_models(
        self,
        *,
        persona_name: Optional[str],
        locale_override: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        mode: str = "persona",
    ) -> bool:
        if self.heavy_models_need_reload(
            persona_name=persona_name, locale_override=locale_override
        ):
            self.load_models(
                on_progress=on_progress,
                mode=mode,
                persona_name=persona_name,
                locale_override=locale_override,
            )
            return True
        return False

    def reload_speech_stack_for_persona(
        self,
        *,
        persona_name: Optional[str],
        locale_override: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> None:
        was_running = self._running
        if was_running:
            self.stop()
        self.load_models(
            on_progress=on_progress,
            mode="persona",
            persona_name=persona_name,
            locale_override=locale_override,
        )
        if was_running:
            self.start("persona", persona_name=persona_name)

    def start(
        self,
        mode: str = "persona",
        *,
        persona_name: Optional[str] = None,
        session_name: Optional[str] = None,
    ) -> None:
        if self._running:
            raise PipelineAlreadyRunningError("Pipeline is already running")

        logger.info("PipelineController starting in %r mode", mode)
        self._mode = mode

        if mode == "persona":
            self._start_persona_mode(persona_name=persona_name)
        elif mode == "transcribe":
            self._start_transcribe_mode(session_name=session_name)
        else:
            raise ValueError(f"Unknown mode: {mode!r}")

        self._running = True
        logger.info("PipelineController started in %r mode", mode)
        if mode == "persona":
            self._callbacks.on_status("Mic open. Listening.")
        elif mode == "transcribe":
            self._callbacks.on_status(
                "Transcribe mode — mic open. Ctrl+C to stop."
            )

    def stop(self) -> None:
        if not self._running:
            return

        logger.info("PipelineController stopping (mode=%r)", self._mode)
        self._callbacks.on_status("Stopping pipeline...")

        if self._capture is not None:
            self._capture.stop()
            self._capture = None

        if self._audio_queue is not None:
            _put_shutdown_sentinel(self._audio_queue)

        # Persona mode: two threads — transcription must finish before reaction gets its sentinel
        if self._mode == "persona" and len(self._threads) >= 2:
            t_transcription, t_reaction = self._threads[0], self._threads[1]

            t_transcription.join(timeout=120.0)
            if t_transcription.is_alive():
                logger.warning("heckler-transcription thread did not stop within 120s")
                self._callbacks.on_status("Waiting for transcription worker shutdown...")

            if self._reaction_queue is not None:
                _put_shutdown_sentinel(self._reaction_queue)

            t_reaction.join(timeout=120.0)
            if t_reaction.is_alive():
                logger.warning("heckler-reaction thread did not stop within 120s")
                self._callbacks.on_status("Waiting for reaction worker shutdown...")

        else:
            for t in self._threads:
                t.join(timeout=120.0)
                if t.is_alive():
                    logger.warning("Thread %r did not stop within 120s", t.name)

        # Transcribe-mode session cleanup
        if (
            self._mode == "transcribe"
            and self._transcript_conn is not None
            and self._transcript_session_id is not None
        ):
            close_session(self._transcript_conn, self._transcript_session_id)
            label = self._transcript_session_label or self._transcript_session_id[:8]
            export_path = Path(self._config.transcripts_dir) / f"{label}.md"
            try:
                export_session_markdown(
                    self._transcript_conn, self._transcript_session_id, export_path
                )
            except (OSError, RuntimeError, sqlite3.Error):
                logger.exception(
                    "transcribe mode: markdown export failed",
                    extra={"session_id": self._transcript_session_id},
                )
            self._callbacks.on_status(
                "Transcribe session ended "
                f"(id={self._transcript_session_id}, markdown={export_path})"
            )
            self._transcript_conn = None
            self._transcript_session_id = None
            self._transcript_session_label = None

        self._threads = []
        self._audio_queue = None
        self._reaction_queue = None
        self._reactor_holder = None
        self._running = False

        logger.info("PipelineController stopped")

    def switch_mode(
        self,
        new_mode: str,
        *,
        persona_name: Optional[str] = None,
        session_name: Optional[str] = None,
    ) -> None:
        if not self._running:
            raise PipelineNotRunningError("Cannot switch mode: pipeline is not running")
        logger.info("PipelineController switching from %r to %r", self._mode, new_mode)
        self.stop()
        if new_mode == "persona":
            self.ensure_heavy_models(
                persona_name=persona_name,
                locale_override=None,
                mode="persona",
            )
        self.start(new_mode, persona_name=persona_name, session_name=session_name)

    def swap_persona(self, persona_name: str) -> None:
        """Hot-swap Reactor prompts/config gates only (same speech-stack signature).

        Caller guarantees speech-stack signature is unchanged; raises
        ``PipelineNotRunningError`` if not running. Cross-locale reload is handled
        by GUI ``_apply_persona_and_speech`` (not ``swap_persona``).
        """
        if not self._running:
            raise PipelineNotRunningError("Cannot swap persona: pipeline is not running")
        if self._mode != "persona":
            raise PipelineNotRunningError("swap_persona requires persona mode")

        prompts_root = Path(__file__).resolve().parent.parent / "prompts"
        persona = load_persona(prompts_root / persona_name)
        cfg = apply_persona_overrides(self._config, persona)
        new_reactor = Reactor(cfg, persona.system_prompt, persona.examples)

        assert self._reactor_holder is not None
        self._reactor_holder.swap(new_reactor)
        self._persona_name = persona_name
        logger.info("Persona swapped to %r", persona_name)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_mode(self) -> Optional[str]:
        return self._mode

    @property
    def current_persona_name(self) -> Optional[str]:
        return self._persona_name

    # ------------------------------------------------------------------
    # Internal startup helpers
    # ------------------------------------------------------------------

    def _start_persona_mode(self, *, persona_name: Optional[str] = None) -> None:
        assert self._transcriber is not None, "load_models() must be called before start()"
        assert self._speaker is not None, (
            "Speaker not loaded. Call load_models() without mode restriction "
            "(default loads TTS), before starting persona mode."
        )

        effective_persona_name = persona_name or self._config.persona_name
        prompts_root = Path(__file__).resolve().parent.parent / "prompts"
        persona = load_persona(prompts_root / effective_persona_name)
        cfg = apply_persona_overrides(self._config, persona)
        self._persona_name = persona.name

        heckler_logger = HecklerLogger(cfg)
        reactor = Reactor(cfg, persona.system_prompt, persona.examples)
        self._reactor_holder = ReactorHolder(reactor)
        context_buffer = ContextBuffer(cfg.context_window_size)
        pacing_gate = PacingGate(cfg)

        audio_queue: queue.Queue = queue.Queue(maxsize=cfg.queue_maxsize)
        reaction_queue: queue.Queue = queue.Queue(maxsize=cfg.queue_maxsize)
        self._audio_queue = audio_queue
        self._reaction_queue = reaction_queue

        # Speaker must be initialized before AudioCapture (is_playing wiring)
        capture = AudioCapture(cfg, audio_queue, self._speaker.is_playing)
        self._capture = capture

        transcription_thread = threading.Thread(
            target=_run_transcription_worker,
            kwargs={
                "config": cfg,
                "audio_queue": audio_queue,
                "reaction_queue": reaction_queue,
                "transcriber": self._transcriber,
                "heckler_logger": heckler_logger,
                "on_transcript": self._callbacks.on_transcript,
            },
            name="heckler-transcription",
            daemon=False,
        )
        reaction_thread = threading.Thread(
            target=_run_reaction_worker,
            kwargs={
                "context_buffer": context_buffer,
                "reactor_holder": self._reactor_holder,
                "pacing_gate": pacing_gate,
                "speaker": self._speaker,
                "heckler_logger": heckler_logger,
                "reaction_queue": reaction_queue,
                "on_reaction": self._callbacks.on_reaction,
            },
            name="heckler-reaction",
            daemon=False,
        )

        transcription_thread.start()
        reaction_thread.start()
        capture.start()

        self._threads = [transcription_thread, reaction_thread]

    def _start_transcribe_mode(self, *, session_name: Optional[str] = None) -> None:
        assert self._transcriber is not None, "load_models() must be called before start()"

        effective_config = dataclasses.replace(
            self._config,
            max_speech_duration_s=self._config.transcribe_max_speech_duration_s,
            silence_duration_ms=self._config.transcribe_silence_duration_ms,
            min_speech_duration_ms=self._config.transcribe_min_speech_duration_ms,
        )

        transcript_conn = open_store(Path(self._config.sqlite_database_path))
        init_transcript_schema(transcript_conn)
        session_id = str(uuid.uuid4())
        session_label = session_name or self._config.session_name or session_id[:8]
        create_session(transcript_conn, session_id=session_id, name=session_label)

        self._transcript_conn = transcript_conn
        self._transcript_session_id = session_id
        self._transcript_session_label = session_label

        audio_queue: queue.Queue = queue.Queue(maxsize=self._config.queue_maxsize)
        self._audio_queue = audio_queue
        self._reaction_queue = None

        # Transcribe mode has no Speaker, so is_playing is a bare unset Event
        is_playing = threading.Event()
        capture = AudioCapture(effective_config, audio_queue, is_playing)
        self._capture = capture
        transcript_lock = threading.Lock()

        transcribe_thread = threading.Thread(
            target=_run_transcribe_worker,
            kwargs={
                "config": self._config,
                "audio_queue": audio_queue,
                "transcriber": self._transcriber,
                "transcript_conn": transcript_conn,
                "session_id": session_id,
                "transcript_lock": transcript_lock,
                "on_transcript": self._callbacks.on_transcript,
            },
            name="heckler-transcribe",
            daemon=False,
        )
        transcribe_thread.start()
        capture.start()

        self._threads = [transcribe_thread]
