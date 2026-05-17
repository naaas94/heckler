# HECKLER

HECKLER is a local reactive audio pipeline for **English** speech. In **persona** mode it listens on the microphone, segments with Silero VAD, transcribes with faster-whisper (CUDA in the intended setup), scores lexical density, asks an LLM (via [LiteLLM](https://github.com/BerriAI/litellm)) for short commentary, applies pacing and quality gates, synthesizes speech with Kokoro, and plays through the default output device. In **transcribe** mode it runs **capture + Whisper only**: utterances print as `[TRANSCRIBE]` lines, chunks are stored in SQLite alongside the main database, and stopping a session writes a **markdown** file under the configured transcripts directory (default `transcripts/`). The default chat model for persona mode is **OpenAI GPT-4o mini** (`openai/gpt-4o-mini`). Persona-mode `HeckleEvent` rows are persisted in **SQLite** (default `logs/heckler.db`); use **`HECKLER_DATABASE_PATH`** to override the database file path (same file holds transcript session tables in transcribe mode).

Run headless from the terminal with `python -m heckler` / the `heckler` console script, or use the **PyQt6** desktop app via the `heckler-gui` console script (mode toggle, persona picker, live feed, transcribe session export).

## Hardware

Target profile for **persona** mode on v1: **Windows**, **NVIDIA RTX 3060 or better** (CUDA for Whisper), and **about 64 GB RAM** for comfortable model residency alongside PyTorch and Kokoro. **Transcribe** mode still wants CUDA for Whisper but skips Kokoro and the LLM at runtime, so memory and GPU headroom requirements are lower. A working microphone is required; speakers or headphones are required for persona mode (TTS playback).

## Setup

1. **CUDA-enabled PyTorch** (CUDA 12.1 wheels). Use the PyTorch index **only** for this step so pip does not substitute an older CPU build from PyPI:

   ```bash
   pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
   ```

2. **Install the project** (includes runtime deps such as faster-whisper, LiteLLM, Kokoro, sounddevice, PyQt6):

   ```bash
   pip install -e ".[dev]"
   ```

   `pyproject.toml` pins **NumPy below 2.x** and **torch 2.5+** so Kokoro’s Transformers stack stays compatible with PyTorch’s attention helpers. If you mix indexes, install PyTorch first as in step 1, then this step from PyPI.

   Persona prompt bundles (`prompts/<persona>/` with `persona.toml`, `system.md`, `examples.json`) live next to the `heckler` package in the repo. **`pip install -e .`** keeps that layout on disk so `python -m heckler` can resolve prompts. A non-editable **`pip install .`** without the checkout does not copy `prompts/` into site-packages; use an editable install from a clone for normal runs.

3. **Environment file**

   Copy `.env.example` to `.env`. For the default `openai/gpt-4o-mini` model, set **`OPENAI_API_KEY`** (or configure credentials the way your OpenAI tooling expects). To use Anthropic, Ollama, or another LiteLLM backend, set **`HECKLER_LLM_MODEL`** to the appropriate LiteLLM model id and provide the matching key or base URL (see the table below). Uncomment optional overrides as needed.

## Configuration (environment variables)

Values are read from `.env` (via `python-dotenv`) in `heckler/config.py` → `load_config()`. `.env.example` shows a minimal subset; any variable below can be set in your own `.env`.

| Variable | Purpose |
|----------|---------|
| `HECKLER_DATABASE_PATH` | SQLite database file path (non-empty overrides default `logs/heckler.db`). Holds persona `HeckleEvent` rows and, in transcribe mode, transcript session/chunk tables. Replaces the retired **`log_dir`** / daily JSONL steady-state sink. |
| `HECKLER_PERSONA` | Persona id for the prompt bundle under `prompts/<name>/` (non-empty after strip overrides default `heckler`; whitespace-only falls back to the default). |
| `HECKLER_MODE` | `persona` or `transcribe` (non-empty after strip; default `persona`). Use CLI `--mode` when you want argparse to enforce the choice. |
| `HECKLER_SESSION_NAME` | Optional default session label for transcribe mode (non-empty after strip; otherwise a short id-derived label is used). |
| `HECKLER_TRANSCRIPTS_DIR` | Directory for transcribe markdown exports (non-empty after strip; default `transcripts`). |
| `HECKLER_LLM_MODEL` | LiteLLM model id (non-empty overrides default `openai/gpt-4o-mini`). |
| `OPENAI_API_KEY` | API key for OpenAI- and Azure-routed LiteLLM models (`openai/...`, `azure/...`); optional if the provider picks up credentials elsewhere. |
| `ANTHROPIC_API_KEY` | API key for `anthropic/...` models; optional if unused or supplied via other means. |
| `OLLAMA_API_BASE` | Base URL for `ollama/...` models when set (e.g. `http://127.0.0.1:11434`). |
| `WHISPER_MODEL` | Whisper model id (default `large-v3`). |
| `SCORE_THRESHOLD` | Minimum LLM self-score to accept commentary (default `0.65`). |
| `PACING_INTERVAL` | Minimum seconds between spoken outputs / cooldown baseline (default `12.0`). |
| `KOKORO_VOICE` | Kokoro voice id (default `af_sarah`). |
| `LOG_DENSITY_FAILURES` | If `true`, persist density-gate rejects via the same SQLite event path as other events; default `false` drops them silently. |

**Optional observability (hosted traces)** — LiteLLM and provider SDKs read these from the process environment when present; heckler does not require them for normal runs.

| Variable | Purpose |
|----------|---------|
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | When both are set, LiteLLM-oriented integrations (e.g. Langfuse) can attach traces to completions. |
| `LANGCHAIN_TRACING_V2` or `LANGSMITH_TRACING` | Truthy values enable LangSmith-style tracing together with an API key below. |
| `LANGCHAIN_API_KEY` / `LANGSMITH_API_KEY` | API key for LangSmith / LangChain tracing when tracing flags are on. |

Additional tuning lives on `HecklerConfig` defaults in `heckler/config.py` (sample rate, VAD thresholds, transcribe-mode timing defaults, queue size, default SQLite path, etc.) but is not all exposed as environment variables in v1.

## Usage

**Persona mode (default)** — full loop with logging to SQLite:

```bash
python -m heckler
```

**Transcribe mode** — Whisper only; stdout lines prefixed with `[TRANSCRIBE]`; SQLite transcript chunks; on orderly shutdown, a markdown file is written under `HECKLER_TRANSCRIPTS_DIR` / default `transcripts/`:

```bash
python -m heckler --mode transcribe
python -m heckler --mode transcribe --session-name standup-notes
```

If you omit `--mode`, the value from `HECKLER_MODE` in the environment is used (default `persona`). `--session-name` overrides `HECKLER_SESSION_NAME` for that run.

List audio devices (uses `sounddevice.query_devices()`):

```bash
python -m heckler --list-devices
```

Select a persona bundle (persona mode only; overrides `HECKLER_PERSONA` / default `heckler` for this process):

```bash
python -m heckler --persona heckler
```

The `heckler` console script entry point resolves to `heckler.pipeline:main`.

Structured persona events are written to the SQLite file configured by `HECKLER_DATABASE_PATH` (default `logs/heckler.db`). Transcribe sessions use the same database file for their own tables. Startup and status lines prefixed with `[HECKLER]` go to stdout and are not stored as persona event rows.

In persisted `HeckleEvent` rows, `cooldown_remaining_at_eval` comes from the **pacing gate** (`PacingGate.evaluate`); optional dataset-style evaluation metadata (when present) uses separate tables such as `heckler_eval_labels`—do not read “eval” in column names as hosted scoring unless you mean that table.

### Legacy JSONL import

Steady-state logging is SQLite only. To load historical `heckler_*.jsonl` lines into the same `events` shape as live logging, from the repo root (after `pip install -e .`):

```bash
python scripts/import_legacy_jsonl.py [--database PATH] [--dry-run] [--skip-existing] FILE [FILE ...]
```

- `--database` / `-d`: SQLite file (default: non-empty `HECKLER_DATABASE_PATH` or `logs/heckler.db`).
- `--dry-run`: parse and validate only; no writes.
- `--skip-existing`: skip lines whose `(utterance_id, timestamp_iso)` pair already exists (uses JSON1 `json_extract` on `payload_json` when needed).

## GUI

Launch the graphical interface:

```bash
heckler-gui
```

The GUI provides:

- **Mode toggle** — switch between persona and transcribe modes at runtime without restarting.
- **Persona picker** — select and hot-swap persona bundles while the pipeline is running.
- **Live feed** — real-time transcript of what is being said, plus AI reactions in persona mode.
- **Session controls** — start/stop transcription sessions and export to markdown (transcribe mode).

The GUI loads **Whisper and Kokoro once** at startup (so you can switch to persona mode without reloading TTS), with a progress indicator in the status bar; first launch still pays Whisper/Kokoro download and cache costs where applicable.

PyQt6 is a core runtime dependency; installing the project with `pip install -e .` or `pip install -e ".[dev]"` (see [Setup](#setup)) pulls it in alongside the audio/ML stack—no separate GUI-only install step.

The `heckler` CLI remains the path for headless use. For transcribe-heavy CLI use, pass `--mode transcribe` so model load skips Kokoro construction entirely.

## First run

On the first launch you should expect **downloads**: Silero VAD weights via `torch.hub`, faster-whisper model files into the Hugging Face cache, and (in persona mode or whenever Kokoro is loaded) Kokoro assets when `Speaker` initializes. A **transcribe-only** CLI run with `--mode transcribe` skips loading Kokoro, so TTS weights are not pulled until you run persona mode or the GUI (which loads both stacks up front). Subsequent starts reuse cached weights where possible.
