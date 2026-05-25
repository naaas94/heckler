# HECKLER

HECKLER is a local reactive audio pipeline for **multilingual speech** (default locale **English**). A single **`locale`** setting keeps faster-whisper and Kokoro aligned.

In **persona** mode it listens on the microphone, segments with Silero VAD, transcribes with faster-whisper (CUDA required today), scores lexical density, asks an LLM ([LiteLLM](https://github.com/BerriAI/litellm)) for short commentary, applies pacing and quality gates, synthesizes speech with Kokoro, and plays through the default output device. The default chat model is **OpenAI GPT-4o mini** (`openai/gpt-4o-mini`). Events are persisted in **SQLite** (default `logs/heckler.db`; override with **`HECKLER_DATABASE_PATH`**).

In **transcribe** mode it runs **capture + Whisper only**: utterances print as `[TRANSCRIBE]` lines, chunks go to SQLite, and stopping a session writes a markdown file under the configured transcripts directory (default `transcripts/`).

Run headless with `python -m heckler` / the `heckler` console script, or use the **PyQt6** desktop app via `heckler-gui` (mode toggle, persona picker, live feed, transcribe export).

## Hardware

Target profile for **persona** mode: **Windows**, **NVIDIA RTX 3060 or better** (CUDA for Whisper), and **about 64 GB RAM** for comfortable model residency alongside PyTorch and Kokoro. **Transcribe** mode still wants CUDA for Whisper but skips Kokoro and the LLM at runtime. A working microphone is required; speakers or headphones are required for persona mode (TTS playback).

Whisper is loaded with **`device="cuda"`** only; there is no CPU fallback in v1.

For persona mode with open speakers, prefer **headphones** or careful routing/gain to limit **TTS bleed into the mic** (echo). The pipeline gates capture during playback and keeps a short post-playback tail (`TTS_GATE_TAIL_MS`), but room bleed can still produce transcripts that repeat the last spoken comment.

## Bundled personas

Each persona is a directory under `prompts/<id>/` centered on `persona.toml` (plus bundled prompt and few-shot assets). Use `--persona <id>`, `HECKLER_PERSONA`, or the GUI picker.

| Id | Locale | Pacing (min interval) | Score gate | Notes |
|----|--------|----------------------|------------|--------|
| `heckler` | English (default) | 12 s | 0.65 | Default deadpan commentator |
| `technician` | English | 6 s | 0.55 | Direct technical corrections; faster cadence |
| `heckler_arg` | Spanish (`es`) | 12 s | 0.65 | Reloads STT/TTS when switching from English personas |

Persona **`[gates]`** and **`[voice]`** / **`[llm]`** tables override `HecklerConfig` when the bundle is loaded. **`[output].comment_types`** in TOML is informational only. Per-persona **capture/VAD** overrides (longer monologues, longer silence before end-of-utterance) are **not** implemented yet—all persona modes share global capture defaults (15 s max speech, 800 ms silence) unless you change code or env-level defaults.

## Setup

1. **CUDA-enabled PyTorch** (CUDA 12.1 wheels). Use the PyTorch index **only** for this step so pip does not substitute an older CPU build from PyPI:

   ```bash
   pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
   ```

2. **Install the project** (includes faster-whisper, LiteLLM, Kokoro, sounddevice, PyQt6; dev extras add pytest):

   ```bash
   pip install -e ".[dev]"
   ```

   `pyproject.toml` pins **NumPy below 2.x** and **torch 2.5+** for Kokoro’s Transformers stack. Install PyTorch first as in step 1, then this step from PyPI.

   Persona bundles live next to the `heckler` package in the repo. **`pip install -e .`** keeps that layout on disk. A non-editable **`pip install .`** without the checkout does not copy `prompts/` into site-packages—use an editable install from a clone.

3. **Environment file**

   Copy `.env.example` to `.env`. Set **`OPENAI_API_KEY`** for the default model, or set **`HECKLER_LLM_MODEL`** plus the matching provider key or base URL (see table below).

## Configuration (environment variables)

Values are read from `.env` via `python-dotenv` in `heckler/config.py` → `load_config()`.

| Variable | Purpose |
|----------|---------|
| `HECKLER_DATABASE_PATH` | SQLite path (default `logs/heckler.db`). Persona events and transcribe session tables share this file. |
| `HECKLER_PERSONA` | Persona id under `prompts/<name>/` (default `heckler`). |
| `HECKLER_MODE` | `persona` or `transcribe` (default `persona`). CLI `--mode` enforces valid choices. |
| `HECKLER_LOCALE` | Unified STT/TTS locale slug (default `en`). Unknown slugs raise `UnsupportedLocaleError` at load. Do not set separate Whisper or Kokoro language env vars. |
| `HECKLER_SESSION_NAME` | Optional default label for transcribe sessions. |
| `HECKLER_TRANSCRIPTS_DIR` | Transcribe markdown export directory (default `transcripts`). |
| `HECKLER_LLM_MODEL` | LiteLLM model id (default `openai/gpt-4o-mini`). |
| `OPENAI_API_KEY` | For `openai/...` and `azure/...` models. |
| `ANTHROPIC_API_KEY` | For `anthropic/...` models. |
| `OLLAMA_API_BASE` | For `ollama/...` (e.g. `http://127.0.0.1:11434`). |
| `WHISPER_MODEL` | Whisper model id (default `large-v3`). |
| `SCORE_THRESHOLD` | Minimum LLM self-score to accept commentary (default `0.65`). |
| `PACING_INTERVAL` | Minimum seconds between spoken outputs (default `12.0`; personas can override via TOML `pacing_interval`). |
| `KOKORO_VOICE` | Kokoro voice id (default `af_sarah`). |
| `TTS_GATE_TAIL_MS` | Ms to keep the mic gate after TTS ends (default `400`; `0` clears immediately). While gated, capture does not accumulate VAD segments. |
| `LOG_DENSITY_FAILURES` | If `true`, persist density-gate rejects to SQLite; default `false` drops them. |

**Optional observability** — LiteLLM and provider SDKs read these when set; not required for normal runs.

| Variable | Purpose |
|----------|---------|
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Langfuse-style tracing when both are set. |
| `LANGCHAIN_TRACING_V2` or `LANGSMITH_TRACING` | Enable LangSmith-style tracing. |
| `LANGCHAIN_API_KEY` / `LANGSMITH_API_KEY` | API key when tracing flags are on. |

### Persona TOML overrides

Mapped keys in `persona.toml` (other keys log a warning and are ignored):

| TOML section.key | `HecklerConfig` field |
|------------------|----------------------|
| `[voice].kokoro_voice` | `kokoro_voice` |
| `[voice].kokoro_speed` | `kokoro_speed` |
| `[voice].locale` | `locale` → resolves whisper + Kokoro codes |
| `[llm].model` | `llm_model` |
| `[llm].temperature` | `llm_temperature` |
| `[llm].max_tokens` | `llm_max_tokens` |
| `[gates].score_threshold` | `score_threshold` |
| `[gates].pacing_interval` | `min_output_interval_s` |
| `[gates].density_threshold` | `density_threshold` |
| `[gates].min_word_count` | `min_word_count` |

### Defaults not exposed as environment variables

Set in code or by editing `HecklerConfig` construction if you extend the app:

| Field | Default | Role |
|-------|---------|------|
| `score_override_threshold` | `0.90` | After a successful LLM reaction, bypass post-LLM pacing cooldown when score ≥ this (does **not** apply on pre-LLM cooldown skip). |
| `density_threshold` | `0.40` | Semantic gate minimum lexical density. |
| `min_word_count` | `4` | Semantic gate minimum words. |
| `context_window_size` | `5` | Utterances in rolling LLM context (not stored on each event row). |
| `max_speech_duration_s` | `15.0` | Persona-mode VAD max segment length. |
| `silence_duration_ms` | `800` | Persona-mode silence before segment end. |
| `transcribe_max_speech_duration_s` | `45.0` | Transcribe-mode max segment length. |
| `transcribe_silence_duration_ms` | `1500` | Transcribe-mode silence threshold. |
| `whisper_compute_type` | `int8_float16` | faster-whisper compute type. |

### Locale (STT + TTS)

Supported slugs at load time (`heckler/locale.py`):

| Locale slug | Whisper language | Kokoro `lang_code` |
|-------------|------------------|--------------------|
| `en` | `en` | `a` (American English) |
| `en-us` | `en` | `a` |
| `en-gb` | `en` | `b` (British English) |
| `es` | `es` | `e` (Spanish) |

- **`HECKLER_LOCALE`** sets the process default. In the GUI, **Speech locale** can override; **From persona** uses the selected persona’s `[voice].locale`.
- Persona locale is applied when heavy models are built (`load_models`, `ensure_heavy_models`, or GUI reload).

### Persona locale and reload

Reload is keyed on **`(whisper_language, kokoro_lang_code)`** (`speech_stack_signature` in `heckler/locale.py`). Kokoro **voice** is not part of the signature.

| Change | Behavior |
|--------|----------|
| Same signature (e.g. `heckler` → `technician`) | **Hot-swap**: Reactor only; Whisper/Kokoro stay loaded. |
| Different signature (e.g. `heckler` → `heckler_arg`) | **Reload** Whisper + Kokoro (~20–60 s). GUI asks while running; **Start** reloads when idle. |
| Voice-only, same locale | No reload. |
| Re-select same persona | No-op. |

**GUI:** Persona picker + **Speech locale** before **Start**, or change while running (reload dialog when needed). **Reload speech models** forces reload. **`HECKLER_LOCALE`** is the base; **From persona** does not pass a slug (persona TOML wins).

**CLI:** `python -m heckler --persona heckler_arg` loads Spanish STT/TTS at startup. No interactive hot-swap on CLI—restart with another `--persona` or `HECKLER_LOCALE`.

### Pacing and GUI callbacks

During persona-mode **cooldown** (minimum interval since last spoken output), the pipeline may **skip the LLM entirely** (`PacingGate.cooldown_status`). `score_override_threshold` applies only on the **post-LLM** path (`PacingGate.evaluate` after `react()`).

The GUI **reaction preview** (`on_reaction`) runs only when a `ReactorResult` exists—post-LLM paths including post-LLM pacing rejects—not on pre-LLM pacing rejects.

## Usage

**Persona mode (default):**

```bash
python -m heckler
python -m heckler --persona technician
```

**Transcribe mode:**

```bash
python -m heckler --mode transcribe
python -m heckler --mode transcribe --session-name standup-notes
```

If you omit `--mode`, `HECKLER_MODE` is used (default `persona`).

**List audio devices:**

```bash
python -m heckler --list-devices
```

The `heckler` entry point is `heckler.pipeline:main`. Status lines prefixed `[HECKLER]` go to stdout and are not stored as persona events.

### SQLite and evaluation

Persona rows live in `events` with normalized gate/latency columns and JSON in `payload_json`. Optional child table **`event_reactor_results`** holds comment, score, and type when the reactor ran. **`heckler_eval_labels`** is reserved for human quality labels (`positive` / `negative` / `skip`); there is **no built-in labeling tool yet**—use SQL or your own script against `events.id`.

**Pacing analytics:** Pre-LLM pacing rejects have no reactor row and `llm_latency_ms` is null. Post-LLM pacing rejects include full reactor payload but `spoken=0`. Column `cooldown_remaining_at_eval` is pacing timing, not human eval scores.

Sub-threshold LLM scores are **not** persisted (no near-miss rows unless you add tooling).

### Legacy JSONL import

Steady-state logging is SQLite only. From the repo root after `pip install -e .`:

```bash
python scripts/import_legacy_jsonl.py [--database PATH] [--dry-run] [--skip-existing] FILE [FILE ...]
```

- `--database` / `-d`: SQLite file (default: `HECKLER_DATABASE_PATH` or `logs/heckler.db`).
- `--dry-run`: parse only.
- `--skip-existing`: skip duplicate `(utterance_id, timestamp_iso)` pairs.

## GUI

```bash
heckler-gui
```

- **Mode toggle** — persona vs transcribe without restart.
- **Persona picker** — hot-swap or reload speech stack as needed.
- **Live feed** — transcript plus reactions in persona mode.
- **Transcribe** — session start/stop and markdown export.

Whisper and Kokoro load once at GUI startup (progress in the status bar). PyQt6 is a core dependency—no separate GUI install. For headless transcribe-only runs, use `python -m heckler --mode transcribe` so Kokoro is not loaded.

## Development

Requires editable install with dev extras (`pip install -e ".[dev]"`).

```bash
pytest
```

GUI tests may need an offscreen platform, for example:

```bash
set QT_QPA_PLATFORM=offscreen
pytest tests/test_gui.py
```

(on Unix-like shells, use `export` instead of `set`).

There is **no CI workflow** in the repository yet; run tests locally before merging.

## First run

Expect **downloads** on first launch: Silero VAD via `torch.hub`, faster-whisper weights (~/.cache/huggingface), and Kokoro assets when `Speaker` loads. Transcribe-only CLI with `--mode transcribe` skips Kokoro until persona mode or the GUI runs. Later starts reuse caches where possible.
