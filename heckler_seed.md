Greenfield, so no pre-plan exploration needed. Here's the full spec document to feed directly to the orchestrator.

---

# HECKLER — Orchestrator Input Spec

**Plan name:** `heckler-v1`
**Language:** Python 3.11+
**Target hardware:** RTX 3060, Ryzen 5, 64GB RAM, Windows (assumed — flag if Linux)
**Repository root:** `heckler/` (new repo, greenfield)
**Readiness verdict:** READY

---

## §0 — System Description

HECKLER is a local reactive audio commentary loop. It captures microphone input continuously, segments on silence boundaries, transcribes via local Whisper, generates a snarky/sarcastic comment via a cloud LLM (with a self-assessed funniness score), applies threshold and pacing gates, synthesizes speech via local TTS, and plays back through system audio. Every event is logged to JSONL regardless of whether it results in playback. The system does not converse — it heckles.

**Primary constraint:** End-to-end latency (mic input → audio playback start) must stay under 2.5 seconds for a typical 5–10 word utterance. This is a soft SLA, not a hard kill criterion, but all implementation decisions should be evaluated against it.

---

## §1 — Repository Layout

```
heckler/
├── heckler/
│   ├── __init__.py
│   ├── config.py           # all tunables, loaded once at startup
│   ├── models.py           # shared dataclasses and enums
│   ├── audio_capture.py    # VAD-segmented mic capture → queue
│   ├── transcriber.py      # faster-whisper wrapper
│   ├── semantic_gate.py    # lexical density filter, pre-LLM
│   ├── context_buffer.py   # rolling utterance window
│   ├── reactor.py          # LLM call, structured output, score gate
│   ├── pacing_gate.py      # cooldown + score-override logic
│   ├── speaker.py          # TTS synthesis + mic gate + playback
│   ├── logger.py           # append-only JSONL event logger
│   └── pipeline.py         # thread orchestration, queue wiring, entrypoint
├── prompts/
│   ├── system.md           # character contract — loaded at startup
│   └── examples.json       # few-shot examples — loaded at startup
├── logs/                   # runtime JSONL output, gitignored
├── tests/
│   ├── test_semantic_gate.py
│   ├── test_pacing_gate.py
│   ├── test_reactor.py     # mocked LLM
│   └── test_models.py
├── pyproject.toml
├── .env.example
└── README.md
```

---

## §2 — Shared Contracts (`models.py`)

This file is the single source of truth for all inter-module data shapes. No module defines its own local dataclasses for cross-boundary data. Every module imports from here.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

class CommentType(str, Enum):
    SARCASM = "sarcasm"
    CALLBACK = "callback"
    OBSERVATION = "observation"
    ABSURDIST = "absurdist"
    PASSIVE_AGGRESSIVE = "passive_aggressive"
    UNKNOWN = "unknown"

class DiscardReason(str, Enum):
    DENSITY_GATE = "density_gate"       # failed semantic density threshold
    SCORE_GATE = "score_gate"           # LLM score below threshold
    PACING_GATE = "pacing_gate"         # too soon after last output
    LLM_ERROR = "llm_error"             # LLM call failed or unparseable
    TTS_ERROR = "tts_error"             # TTS synthesis failed

@dataclass
class AudioChunk:
    audio: "np.ndarray"    # float32, shape (N,), sample_rate=16000
    captured_at: float     # time.time() at capture boundary

@dataclass
class Utterance:
    utterance_id: str          # uuid4
    transcript: str
    semantic_density: float
    transcribed_at: float      # time.time()
    audio_chunk: AudioChunk    # kept for potential future use / debug

@dataclass
class ReactorResult:
    comment: str
    score: float               # 0.0–1.0, LLM self-assessed
    comment_type: CommentType
    raw_response: str          # verbatim LLM output, for logging

@dataclass
class HeckleEvent:
    """
    Canonical log record. Written to JSONL for every utterance
    that passes the density gate, regardless of downstream outcome.
    """
    utterance_id: str
    timestamp_iso: str                       # ISO 8601
    transcript: str
    semantic_density: float
    passed_density_gate: bool
    reactor_result: Optional[ReactorResult]  # None if LLM errored
    passed_score_gate: Optional[bool]        # None if LLM errored
    passed_pacing_gate: Optional[bool]       # None if score_gate failed
    spoken: bool
    discard_reason: Optional[DiscardReason]
    cooldown_remaining_at_eval: Optional[float]  # seconds remaining in cooldown
    llm_latency_ms: Optional[float]
    tts_latency_ms: Optional[float]
```

**Constraint:** `HeckleEvent` is the only struct written to JSONL. No ad-hoc dict construction in logger.py. Serialization is `dataclasses.asdict()` with enum `.value` coercion.

---

## §3 — Configuration (`config.py`)

All tunables in one place. Loaded once at process start from environment variables with defaults. No config file (env vars only — `.env` loaded via `python-dotenv`).

```python
from dataclasses import dataclass
import os
from typing import Optional

from dotenv import load_dotenv

@dataclass(frozen=True)
class HecklerConfig:
    # Audio capture
    sample_rate: int = 16_000          # Hz — Whisper native, do not change
    capture_device: Optional[int] = None  # None = system default
    vad_threshold: float = 0.5         # silero confidence threshold [0,1]
    min_speech_duration_ms: int = 500  # discard shorter chunks
    max_speech_duration_s: float = 15.0  # force-flush if VAD never closes
    silence_duration_ms: int = 800     # silence window that triggers segment close

    # Transcription
    whisper_model_size: str = "large-v3"
    whisper_compute_type: str = "int8_float16"
    whisper_beam_size: int = 3
    whisper_language: str = "en"

    # Semantic gate
    density_threshold: float = 0.40
    min_word_count: int = 4

    # Context buffer
    context_window_size: int = 5       # last N utterances passed to LLM

    # Reactor (LLM) — LiteLLM model ids, e.g. openai/gpt-4o-mini, anthropic/claude-3-5-haiku-20241022
    llm_model: str = "openai/gpt-4o-mini"
    llm_max_tokens: int = 150          # comments are short; hard cap
    llm_temperature: float = 0.9       # higher = more creative, needed for humor
    score_threshold: float = 0.65      # minimum score to pass to pacing gate
    score_override_threshold: float = 0.90  # bypasses pacing gate if score >= this
    anthropic_api_key: str = ""        # ANTHROPIC_API_KEY when using anthropic/... models
    openai_api_key: str = ""           # OPENAI_API_KEY when using openai/... (or env defaults)
    ollama_api_base: str = ""          # OLLAMA_API_BASE for ollama/... when set

    # Pacing gate
    min_output_interval_s: float = 12.0  # cooldown between spoken outputs

    # TTS
    kokoro_voice: str = "af_sarah"     # dry/deadpan voice — see voice selection note
    kokoro_speed: float = 1.05         # slightly faster than neutral; snappy

    # Logging
    log_dir: str = "logs"
    log_density_failures: bool = False  # if True, also log pre-density-gate drops

    # Pipeline
    queue_maxsize: int = 10            # max backlog per queue; oldest dropped if exceeded


def load_config() -> HecklerConfig:
    load_dotenv()
    llm_env = (os.getenv("HECKLER_LLM_MODEL") or "").strip()
    llm_model = llm_env if llm_env else "openai/gpt-4o-mini"
    return HecklerConfig(
        llm_model=llm_model,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        ollama_api_base=os.getenv("OLLAMA_API_BASE", ""),
        whisper_model_size=os.getenv("WHISPER_MODEL", "large-v3"),
        score_threshold=float(os.getenv("SCORE_THRESHOLD", "0.65")),
        min_output_interval_s=float(os.getenv("PACING_INTERVAL", "12.0")),
        kokoro_voice=os.getenv("KOKORO_VOICE", "af_sarah"),
        log_density_failures=os.getenv("LOG_DENSITY_FAILURES", "false").lower() == "true",
    )
```

**Note on `llm_model`:** Default is **`openai/gpt-4o-mini`** (LiteLLM). Override with **`HECKLER_LLM_MODEL`** for other providers; supply the matching API key or base URL env vars (see `README.md` / `.env.example`).

---

## §4 — Module Specs

### 4.1 `audio_capture.py`

**Responsibility:** Continuous microphone capture with VAD segmentation. Produces `AudioChunk` objects on silence boundaries. Writes to a `queue.Queue`. Does not know about transcription, LLM, or any downstream component.

**Dependencies:** `sounddevice`, `numpy`, `torch` (silero-vad loaded via `torch.hub`)

**Key design decisions:**
- silero-vad v4 runs as a stateful iterator — it maintains frame-level state between calls. Do not reinitialize per chunk. One model instance per capture session.
- Capture is in 30ms frames (480 samples at 16kHz) — the minimum frame size silero-vad accepts. Accumulate frames into a speech buffer while VAD returns `True`. On first `False` after a speech segment, wait `silence_duration_ms` before closing the chunk.
- If `max_speech_duration_s` is exceeded with no silence, force-close the current chunk. Prevents unbounded buffer on continuous monologues.
- Chunk audio must be `float32` in range `[-1.0, 1.0]`. `sounddevice` returns this natively with `dtype='float32'`.

```python
class AudioCapture:
    def __init__(self, config: HecklerConfig, out_queue: queue.Queue) -> None: ...

    def start(self) -> None:
        """Starts capture in a background thread. Non-blocking."""

    def stop(self) -> None:
        """Signals capture thread to stop. Blocks until thread joins."""

    def _capture_loop(self) -> None:
        """
        Internal. Runs in background thread.
        Opens sounddevice InputStream with callback.
        On each VAD-boundary, constructs AudioChunk and puts to out_queue.
        If out_queue is full (maxsize reached), drops oldest item (not newest).
        """

    def _vad_callback(self, indata: np.ndarray, frames: int, ...) -> None:
        """sounddevice callback — must be fast, no blocking I/O here."""
```

**Silero-vad loading:**
```python
# Load once, cache on disk via torch.hub
model, utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False,
    onnx=False  # use torch version for CUDA
)
(get_speech_timestamps, _, read_audio, *_) = utils
```

**Constraint:** The callback thread (`_vad_callback`) must not block. All queue puts happen in the capture loop, not in the callback. The callback writes to an internal ring buffer; the loop drains it.

---

### 4.2 `transcriber.py`

**Responsibility:** Consumes `AudioChunk` from a queue, produces `(utterance_id, transcript, density_score)` tuples. Does not apply the density gate — that's `semantic_gate.py`. Transcriber's job is audio → text, nothing else.

**Dependencies:** `faster-whisper`, `numpy`

```python
class Transcriber:
    def __init__(self, config: HecklerConfig) -> None:
        """
        Loads WhisperModel at init time. This takes 3–8 seconds on first run
        (model download + CUDA initialization). After first load, subsequent
        startups use the cached model from ~/.cache/huggingface/.
        Log a clear "loading transcription model..." message so the operator
        knows startup is not hung.
        """

    def transcribe(self, chunk: AudioChunk) -> str:
        """
        Synchronous. Runs faster-whisper on chunk.audio.
        Returns transcript string. Empty string if VAD passes but whisper
        produces no segments (silence artifact).

        Implementation:
        segments, info = self.model.transcribe(
            chunk.audio,
            beam_size=config.whisper_beam_size,
            language=config.whisper_language,
            vad_filter=True,     # second-pass VAD inside whisper — catches residual
            word_timestamps=False,
            condition_on_previous_text=False  # IMPORTANT: no context leakage between chunks
        )
        return " ".join(seg.text.strip() for seg in segments)
        """

    def run(self, in_queue: queue.Queue, out_queue: queue.Queue) -> None:
        """
        Blocking loop. Called in its own thread by pipeline.py.
        Drains in_queue, transcribes, puts (utterance_id, transcript) to out_queue.
        """
```

**Critical:** `condition_on_previous_text=False` is mandatory. Without it, Whisper hallucinates continuations of previous chunks. Each chunk must be transcribed independently.

**VRAM note:** `large-v3` in `int8_float16` uses ~1.5GB VRAM. Your 3060 has 12GB — no issue. `medium` uses ~0.8GB and runs ~30% faster; acceptable fallback if latency is tight.

---

### 4.3 `semantic_gate.py`

**Responsibility:** Pure synchronous filter. Takes a transcript string, returns `(passes: bool, density: float)`. No I/O, no state, no dependencies outside stdlib.

```python
STOPWORDS: frozenset[str] = frozenset({
    "the","a","an","is","it","and","or","but","in","on","at","to","of",
    "i","you","we","they","he","she","this","that","was","are","be",
    "have","has","had","do","did","so","just","yeah","okay","uh","um",
    "like","you know","right","well","actually","basically","literally"
})

def compute_density(text: str) -> float:
    """
    Lexical density: ratio of non-stopword tokens to total tokens.
    Returns 0.0 for empty or sub-threshold strings.
    Normalizes to lowercase before stopword check.
    Does not stem or lemmatize — intentional, keeps it O(n) and dependency-free.
    """

def passes_gate(text: str, config: HecklerConfig) -> tuple[bool, float]:
    """
    Returns (passes, density_score).
    Fails if:
    - word count < config.min_word_count
    - density < config.density_threshold
    Both checks always run; density is always computed and returned for logging.
    """
```

**Design rationale:** This runs synchronously in the transcription thread before anything goes to the LLM queue. Its job is to prevent the LLM from ever seeing "yeah", "okay so", "uh huh", "mm", and similar zero-information utterances. The threshold is intentionally coarse — it is a noise filter, not a relevance scorer.

**Extended stopwords:** The list above should include common filler words ("like", "you know", "right") as well as grammatical stopwords. Filler words are high-frequency noise in spoken language that a standard NLP stopword list does not cover.

---

### 4.4 `context_buffer.py`

**Responsibility:** Thread-safe rolling window of recent transcripts. Provides formatted context string for LLM prompt injection.

```python
class ContextBuffer:
    def __init__(self, maxlen: int) -> None:
        self._buffer: deque[str] = deque(maxlen=maxlen)
        self._lock: threading.Lock = threading.Lock()

    def push(self, transcript: str) -> None:
        """Thread-safe append."""

    def get_context_block(self) -> str:
        """
        Returns the last N transcripts formatted as a numbered block
        for prompt injection. Thread-safe snapshot.

        Format:
        [1] first utterance
        [2] second utterance
        ...
        [N] most recent utterance

        Returns empty string if buffer is empty.
        Empty-buffer case must be handled gracefully in reactor prompt assembly —
        context block is optional, not required.
        """
```

**Why not pass raw deque to reactor:** Formatting belongs here, not scattered across prompt assembly. The reactor receives a string, period.

---

### 4.5 `reactor.py`

**Responsibility:** Assembles the LLM prompt, calls **`litellm.completion`** with OpenAI-style chat messages, parses structured output, applies score gate. Returns **`(ReactorResult | None, float, DiscardReason | None)`** per the shipped contract. This is the highest-latency module — all optimization decisions should prioritize it.

**Dependencies:** `litellm`, `json`, `re` (for fallback parsing)

**Prompt architecture:**

System prompt loaded from `prompts/system.md` at startup. Not hardcoded in source. This allows persona iteration without code changes.

```
# prompts/system.md content (exact):

You are a dry, deadpan commentator overhearing a conversation. 
You observe. You do not perform. You do not explain your jokes.
Your remarks are short — 15 words maximum, strictly enforced.
You react to what was actually said, not to a caricature of it.
You are understated. Specificity beats generality every time.
The remark must be self-contained — no setup, no follow-up expected.

Avoid:
- Rhetorical questions
- The word "really"
- Starting with "Oh" or "Wow"
- Generic sarcasm ("Sure, totally", "Oh yeah, definitely")
- Any remark longer than 15 words

You respond in JSON only. No preamble. No markdown. No explanation.
Schema: {"comment": string, "score": float, "type": string}
Score is your honest assessment of comedic value: 0.0 = not funny, 1.0 = perfect.
Type must be one of: sarcasm, callback, observation, absurdist, passive_aggressive
```

Few-shot examples loaded from `prompts/examples.json` at startup:

```json
[
  {
    "transcript": "I've been debugging this for three hours and I still don't know what's wrong",
    "comment": "Bold of you to assume it's the code.",
    "score": 0.81,
    "type": "sarcasm"
  },
  {
    "transcript": "we should probably document this at some point",
    "comment": "Probably.",
    "score": 0.77,
    "type": "passive_aggressive"
  },
  {
    "transcript": "the architecture is basically just a big caching problem in disguise",
    "comment": "A caching problem with feelings. Progress.",
    "score": 0.79,
    "type": "observation"
  },
  {
    "transcript": "I think we need to have a meeting about the meeting cadence",
    "comment": "The ouroboros of productivity.",
    "score": 0.88,
    "type": "absurdist"
  },
  {
    "transcript": "I mean it works on my machine",
    "comment": "Ship the machine.",
    "score": 0.91,
    "type": "sarcasm"
  }
]
```

**User prompt template (assembled in reactor.py):**

```
Examples of the register and quality bar:

{examples_block}

---

Recent context (last {N} utterances):
{context_block}

Current utterance to react to:
"{current_transcript}"

Respond with JSON only.
```

**`examples_block` format:**
```
Input: "..."
Response: {"comment": "...", "score": 0.81, "type": "sarcasm"}
```

One block per example, separated by blank lines.

**Reactor class:**

```python
class Reactor:
    def __init__(self, config: HecklerConfig) -> None:
        """
        Loads system prompt from prompts/system.md.
        Loads examples from prompts/examples.json.
        Pre-renders examples_block string (static, no per-call overhead).
        """

    def react(
        self,
        utterance: Utterance,
        context_block: str
    ) -> tuple[Optional[ReactorResult], float, Optional[DiscardReason]]:
        """
        Returns (result_or_none, llm_latency_ms, discard_reason_or_none).
        On success: (result, latency_ms, None).

        result is None with a non-None discard_reason if:
          - API call fails (log error, do not raise) → DiscardReason.LLM_ERROR
          - Response is not parseable JSON → DiscardReason.LLM_ERROR
          - score < config.score_threshold (score gate applied HERE) → DiscardReason.SCORE_GATE

        On parse failure: attempt regex fallback to extract JSON object
        from response string before giving up. LLMs occasionally prepend
        a word before the JSON despite instructions.
        """

    def _parse_response(self, raw: str) -> Optional[ReactorResult]:
        """
        1. Try json.loads(raw) directly.
        2. On failure, try regex: r'\{[^}]+\}' to extract first JSON object.
        3. On failure, return None and log raw string.
        Validates: comment is str, score is float in [0,1], type is valid CommentType.
        """
```

**Latency optimization notes:**
- Do not use streaming — `max_tokens=150` means the full response arrives in one shot faster than streaming overhead.
- Use synchronous **`litellm.completion`** in the reactor thread; async is out of scope for v1.
- If latency regularly exceeds 1500ms, try a faster LiteLLM model id (e.g. a smaller OpenAI or Anthropic Haiku routing) and consider lowering `max_tokens` to 100.

---

### 4.6 `pacing_gate.py`

**Responsibility:** Time-based output throttle. Enforces minimum interval between spoken outputs. High-score override bypasses the cooldown.

```python
class PacingGate:
    def __init__(self, config: HecklerConfig) -> None:
        self._last_output_time: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    def evaluate(self, score: float) -> tuple[bool, float]:
        """
        Returns (should_speak, cooldown_remaining).
        cooldown_remaining: seconds left in cooldown at eval time (0.0 if not in cooldown).

        Logic:
          elapsed = time.time() - self._last_output_time
          in_cooldown = elapsed < config.min_output_interval_s
          cooldown_remaining = max(0.0, config.min_output_interval_s - elapsed)

          if not in_cooldown: return True, 0.0
          if score >= config.score_override_threshold: return True, cooldown_remaining
          return False, cooldown_remaining
        """

    def record_output(self) -> None:
        """
        Call immediately before TTS synthesis begins, not after playback ends.
        Rationale: cooldown intent is "don't stack outputs"; if we wait for
        playback to finish, a 3-second TTS output creates an unintended 3s
        offset in the effective interval.
        Thread-safe.
        """
```

---

### 4.7 `speaker.py`

**Responsibility:** TTS synthesis, mic gate management, audio playback. Owns the `is_playing` event that `audio_capture.py` checks.

**Dependencies:** `kokoro`, `sounddevice`, `numpy`, `threading`

```python
# Kokoro usage — pip install kokoro
from kokoro import KPipeline

class Speaker:
    def __init__(self, config: HecklerConfig) -> None:
        """
        Loads KPipeline at init time (slow, do once).
        lang_code='a' for American English.
        Stores is_playing as threading.Event — shared with AudioCapture.
        """
        self.is_playing: threading.Event = threading.Event()

    def speak(self, comment: str) -> float:
        """
        Full synthesis and playback. Returns tts_latency_ms (synthesis time only,
        not playback duration — playback duration is variable and not useful for
        latency budgeting).

        Steps:
        1. self.is_playing.set()  ← gate mic before synthesis starts
        2. Synthesize: generator = self._pipeline(comment, voice=config.kokoro_voice, speed=config.kokoro_speed)
        3. Collect all audio chunks into single np array (Kokoro yields multiple chunks for longer text)
        4. sounddevice.play(audio, samplerate=24000, blocking=True)
        5. If config.tts_gate_tail_ms > 0: time.sleep(tail_ms / 1000) while gate stays set (acoustic bleed buffer)
        6. self.is_playing.clear()  ← ungate mic after playback and optional tail (finally block)

        On synthesis error or sd.play exception: clear is_playing without tail, log, re-raise as SpeakerError.
        """

    def _collect_audio(self, generator) -> np.ndarray:
        """
        Kokoro yields (graphemes, phonemes, audio_chunk) tuples.
        We only care about audio_chunk (float32 numpy array, 24kHz mono).
        Concatenate all chunks into one array for gapless playback.
        """
```

**Mic gate contract:** `is_playing` is a `threading.Event`. `AudioCapture._capture_loop` checks `speaker.is_playing.is_set()` before putting a chunk to the queue. This prevents the system from transcribing its own TTS output. The event is set before synthesis begins, not before playback — this closes a window where synthesis takes 200ms and the mic could capture the first frames of TTS. After digital playback ends, the gate stays set for `config.tts_gate_tail_ms` (default **400** ms, env **`TTS_GATE_TAIL_MS`**, **`0`** disables) so speaker bleed into the mic path does not produce echo transcripts; `speak()` latency return remains synthesis-only and excludes the tail sleep.

**Kokoro sample rate:** Kokoro outputs 24kHz audio. `sounddevice.play()` must receive `samplerate=24000`, not 16000. These are different sample rates in the pipeline (capture=16kHz, playback=24kHz) — the executor must not mix them.

**Voice selection note for `kokoro_voice`:** Available voices include `af_sarah` (dry, neutral female), `am_adam` (deadpan male), `bf_emma` (measured British female). `af_sarah` is the default; its relatively flat affect suits the deadpan persona. The config param is exposed so Ale can tune without code changes.

---

### 4.8 `logger.py`

**Responsibility:** Append-only JSONL event logger. One file per calendar day. Thread-safe.

```python
import json
import dataclasses
from datetime import datetime, timezone
from pathlib import Path
import threading

class HecklerLogger:
    def __init__(self, config: HecklerConfig) -> None:
        """
        Creates log_dir if not exists.
        Opens today's log file in append mode.
        File path: {log_dir}/heckler_{YYYY-MM-DD}.jsonl
        """
        self._lock = threading.Lock()

    def log_event(self, event: HeckleEvent) -> None:
        """
        Serializes HeckleEvent to JSON and appends to log file.
        Uses dataclasses.asdict() then coerces enums to .value strings.
        Adds newline after each record.
        Thread-safe.
        """

    def _serialize(self, event: HeckleEvent) -> str:
        d = dataclasses.asdict(event)
        # Enum fields come out as their string value from asdict
        # because CommentType and DiscardReason inherit from str
        # AudioChunk.audio (numpy array) must be excluded from log
        d.pop("audio_chunk", None)  # do not serialize raw audio
        return json.dumps(d, ensure_ascii=False)
```

**AudioChunk exclusion:** `HeckleEvent.utterance.audio_chunk` contains a numpy array. numpy arrays are not JSON-serializable and raw audio in logs is wasteful. The `_serialize` method must strip `audio_chunk` before serialization. This is the one serialization special case — document it explicitly in the implementation.

---

### 4.9 `pipeline.py`

**Responsibility:** Wires all components. Owns queues. Manages thread lifecycle. Is the entrypoint (`python -m heckler`).

**Threading model:**

```
Thread 1: AudioCapture._capture_loop
    └─► audio_queue (Queue, maxsize=10)

Thread 2: TranscriptionWorker
    ├─ drains audio_queue
    ├─ calls transcriber.transcribe()
    ├─ calls semantic_gate.passes_gate()
    └─► reaction_queue (Queue, maxsize=10) if passes gate

Thread 3: ReactionWorker
    ├─ drains reaction_queue
    ├─ updates context_buffer
    ├─ calls reactor.react()
    ├─ calls pacing_gate.evaluate()
    ├─ calls speaker.speak() if all gates pass
    ├─ calls pacing_gate.record_output() before speak()
    └─► calls logger.log_event() always
```

**No asyncio.** Three threads, two queues, threading primitives only. The system is I/O-bound at the LLM call and CPU-bound at the Whisper call — asyncio provides no benefit here and complicates the mic gate coordination.

**Queue overflow policy:** If a queue reaches `maxsize`, the producer drops the **oldest** item (not the newest). Stale audio is worthless. Implementation: use a non-blocking `queue.put_nowait()` wrapped in a try/except `queue.Full`, then `queue.get_nowait()` + discard + retry. Do not use `block=True` with timeout — this creates head-of-line blocking in the capture callback.

**Startup sequence (order matters):**

```python
def main():
    config = load_config()
    logger = HecklerLogger(config)

    # Initialize heavy models first — fail fast before any audio starts
    transcriber = Transcriber(config)   # loads Whisper to CUDA
    speaker = Speaker(config)           # loads Kokoro
    reactor = Reactor(config)           # loads prompts; LiteLLM at call time

    # Lightweight components
    context_buffer = ContextBuffer(config.context_window_size)
    pacing_gate = PacingGate(config)

    # Queues
    audio_queue = queue.Queue(maxsize=config.queue_maxsize)
    reaction_queue = queue.Queue(maxsize=config.queue_maxsize)

    # Capture last — mic opens here
    capture = AudioCapture(config, audio_queue, speaker.is_playing)

    # Start threads
    ...

    # Block on KeyboardInterrupt
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        capture.stop()
        # drain queues with timeout, then join threads
```

**Startup note:** Whisper + Kokoro combined load time is 8–15 seconds. Print a clear startup banner with stage markers so Ale knows the system is not hung:

```
[HECKLER] Loading transcription model (large-v3 / CUDA)...
[HECKLER] Transcription ready. (4.2s)
[HECKLER] Loading TTS model (Kokoro / af_sarah)...
[HECKLER] TTS ready. (2.1s)
[HECKLER] Mic open. Listening.
```

---

## §5 — Dependency Manifest (`pyproject.toml`)

```toml
[project]
name = "heckler"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
    "sounddevice>=0.4.6",
    "numpy>=1.26",
    "faster-whisper>=1.0.3",
    "litellm>=1.40.0",
    "kokoro>=0.9.2",
    "torch>=2.2.0",           # silero-vad dependency; CUDA build required
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
]

[project.scripts]
heckler = "heckler.pipeline:main"

[tool.setuptools.packages.find]
include = ["heckler*"]
```

**CUDA torch:** The default `pip install torch` installs CPU torch. Executor must install the CUDA 12.1 build explicitly:

```
pip install torch==2.2.0+cu121 --index-url https://download.pytorch.org/whl/cu121
```

This must be in the README's setup instructions. Do not list it in `pyproject.toml` — the CUDA index URL cannot be expressed there cleanly without a custom installer.

**silero-vad:** Not a direct pip dependency — loaded via `torch.hub.load()` at runtime. First run downloads and caches the model. Requires internet on first run, offline thereafter.

---

## §6 — Coupling Surfaces

These are the binding points that can break silently if implementation drifts. The orchestrator should treat each as a shared contract requiring coordinated implementation across the modules it spans.

**Surface 1** · confirmed
```
AudioChunk.audio dtype and shape
  contract: float32 numpy array, 1D, sample_rate=16000Hz
  modules: audio_capture.py (producer) → transcriber.py (consumer)
  failure mode: faster-whisper silently accepts wrong dtype and returns garbage transcripts
```

**Surface 2** · confirmed
```
speaker.is_playing threading.Event
  contract: set before TTS synthesis; cleared after playback plus post-playback acoustic tail (tts_gate_tail_ms, default 400 ms)
  modules: speaker.py (owner) → audio_capture.py (checker)
  failure mode: mic captures TTS output (including speaker bleed after digital playback ends), system heckles itself recursively
  coupling: AudioCapture receives Speaker.is_playing at construction time — not a global
```

**Surface 3** · confirmed
```
Kokoro output sample rate = 24000Hz
  contract: sounddevice.play() must receive samplerate=24000
  modules: speaker.py only, but easy to confuse with capture sample_rate=16000
  failure mode: audio plays back at wrong pitch/speed — 1.5x fast if 16000 passed to 24000 audio
```

**Surface 4** · confirmed
```
LLM response JSON schema
  contract: {"comment": str, "score": float[0,1], "type": CommentType.value}
  modules: prompts/system.md (declares schema) → reactor.py (parses) → models.py (validates type enum)
  failure mode: schema drift between system prompt and reactor parser produces silent parse failures logged as LLM_ERROR
```

**Surface 5** · confirmed
```
HeckleEvent.audio_chunk serialization exclusion
  contract: audio_chunk field must be stripped before JSON serialization
  modules: models.py (field exists) → logger.py (must exclude)
  failure mode: json.dumps() raises TypeError on numpy array; logger crashes silently if exception is swallowed
```

**Surface 6** · confirmed
```
pacing_gate.record_output() call timing
  contract: must be called BEFORE speaker.speak(), not after
  modules: pipeline.py (caller) → pacing_gate.py (state mutation) → speaker.py (downstream)
  failure mode: if called after playback, TTS duration adds to effective cooldown — 10s interval becomes 10+N seconds where N is utterance length
```

---

## §7 — Constraints and Known Risks

**VRAM budget:** Whisper large-v3 int8 (~1.5GB) + Kokoro (~0.5GB) + silero-vad (~0.1GB) = ~2.1GB peak. 3060 has 12GB. Comfortable. If you add any other CUDA model later, re-audit this.

**Windows audio device indexing:** `sounddevice` device indices are not stable across reboots on Windows. Use `config.capture_device = None` (system default) for initial development. Expose device enumeration as a CLI utility (`python -m heckler --list-devices`) so Ale can set the correct index for multi-device setups.

**Whisper hallucination on silence artifacts:** Even with `vad_filter=True`, Whisper occasionally produces hallucinated text ("Thank you.", "Bye.", "you") on near-silence chunks that silero-vad incorrectly classified as speech. The semantic gate catches most of these (word count < 4), but consider adding a hallucination blocklist of Whisper's known phantom outputs for the remainder.

**Kokoro first-run:** Kokoro downloads model weights (~300MB) on first import if not cached. This happens at `Speaker.__init__()` — add a "downloading TTS model" log message before instantiation so startup doesn't appear hung.

**LLM self-score calibration:** The `score_threshold = 0.65` default is untested against real speech. Initial runs will almost certainly require threshold adjustment. The logging schema captures scores on all discarded events — use the first session's JSONL to calibrate before tuning personas.

**Thread safety of deque:** Python's `deque` is not fully thread-safe for concurrent append + iteration. `ContextBuffer` must use a `threading.Lock` around both `push()` and `get_context_block()`. Do not rely on GIL protection here.

---

## §8 — Implementation Order (Sequencing for Executor)

```
T1: models.py + config.py          ← no dependencies, defines contracts for all others
T2: semantic_gate.py               ← depends on models.py only, fully unit-testable
T3: context_buffer.py              ← depends on stdlib only
T4: logger.py                      ← depends on models.py
T5: audio_capture.py               ← depends on config.py, models.py, sounddevice, silero
T6: transcriber.py                 ← depends on models.py, faster-whisper
T7: pacing_gate.py                 ← depends on models.py, config.py
T8: reactor.py + prompts/          ← depends on models.py, anthropic client
T9: speaker.py                     ← depends on config.py, kokoro, sounddevice
T10: pipeline.py                   ← depends on all of the above; integration point
T11: tests/                        ← T2, T7, T8 (mocked) are highest priority
```

**Parallelization note for orchestrator:** T2, T3, T4 can execute in parallel after T1 completes. T5–T9 can execute in parallel after T1. T10 is strictly last. T11 should be written alongside T2, T7, T8 — not after T10.

---

## §9 — Test Contracts

**`test_semantic_gate.py`:** Table-driven. Must cover: empty string, single word, all-stopword string, filler-word string, normal sentence, boundary cases around `min_word_count` and `density_threshold`. No mocking required.

**`test_pacing_gate.py`:** Must cover: first call (no cooldown), call within cooldown, call after cooldown expires, score override within cooldown, score override above threshold, thread-safety (two threads calling `evaluate()` simultaneously). Use `time.sleep()` sparingly — prefer monkeypatching `time.time`.

**`test_reactor.py`:** Must mock **`litellm.completion`** (or the project’s stable import site used by `Reactor.react`). Cover: valid JSON response, response with leading text before JSON (fallback regex path), invalid JSON (returns None with **`LLM_ERROR`**), score below threshold (returns None with **`SCORE_GATE`**), score at exactly threshold (passes — inclusive), API exception (returns None with **`LLM_ERROR`**, does not raise).

**`test_models.py`:** Serialization round-trip for `HeckleEvent`. Confirm `audio_chunk` is excluded from serialized output. Confirm enum fields serialize to string values.