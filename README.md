# HECKLER

HECKLER is a local, console-only reactive audio loop for English speech: it listens on the microphone, segments utterances with Silero VAD, transcribes with faster-whisper on CUDA, scores lexical density, asks an LLM (via [LiteLLM](https://github.com/BerriAI/litellm)) for short commentary, applies pacing and quality gates, synthesizes speech with Kokoro, and plays through the default output device. The default chat model is **OpenAI GPT-4o mini** (`openai/gpt-4o-mini`). Every handled utterance ends up as one JSON line (a `HeckleEvent`) under `logs/` regardless of whether anything was spoken.

## Hardware

Target profile for v1: **Windows**, **NVIDIA RTX 3060 or better** (CUDA for Whisper), and **about 64 GB RAM** for comfortable model residency alongside torch and Kokoro. A working microphone and speakers/headphones are required.

## Setup

1. **CUDA-enabled PyTorch** (CUDA 12.1 wheels). Use the PyTorch index **only** for this step so pip does not substitute an older CPU build from PyPI:

   ```bash
   pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
   ```

2. **Install the project** (includes runtime deps such as faster-whisper, LiteLLM, Kokoro, sounddevice):

   ```bash
   pip install -e ".[dev]"
   ```

   `pyproject.toml` pins **NumPy below 2.x** and **torch 2.5+** so Kokoro’s Transformers stack stays compatible with PyTorch’s attention helpers. If you mix indexes, install PyTorch first as in step 1, then this step from PyPI.

3. **Environment file**

   Copy `.env.example` to `.env`. For the default `openai/gpt-4o-mini` model, set **`OPENAI_API_KEY`** (or configure credentials the way your OpenAI tooling expects). To use Anthropic, Ollama, or another LiteLLM backend, set **`HECKLER_LLM_MODEL`** to the appropriate LiteLLM model id and provide the matching key or base URL (see the table below). Uncomment optional overrides as needed.

## Configuration (environment variables)

Defined in `.env` / `.env.example` and read in `heckler/config.py` → `load_config()`:

| Variable | Purpose |
|----------|---------|
| `HECKLER_LLM_MODEL` | LiteLLM model id (non-empty overrides default `openai/gpt-4o-mini`). |
| `OPENAI_API_KEY` | API key for OpenAI- and Azure-routed LiteLLM models (`openai/...`, `azure/...`); optional if the provider picks up credentials elsewhere. |
| `ANTHROPIC_API_KEY` | API key for `anthropic/...` models; optional if unused or supplied via other means. |
| `OLLAMA_API_BASE` | Base URL for `ollama/...` models when set (e.g. `http://127.0.0.1:11434`). |
| `WHISPER_MODEL` | Whisper model id (default `large-v3`). |
| `SCORE_THRESHOLD` | Minimum LLM self-score to accept commentary (default `0.65`). |
| `PACING_INTERVAL` | Minimum seconds between spoken outputs / cooldown baseline (default `12.0`). |
| `KOKORO_VOICE` | Kokoro voice id (default `af_sarah`). |
| `LOG_DENSITY_FAILURES` | If `true`, log density-gate rejects as JSONL events; default `false` drops them silently. |

Additional tuning lives on `HecklerConfig` defaults in `heckler/config.py` (sample rate, VAD thresholds, queue size, log directory, etc.) but is not overridden via `.env.example` in v1.

## Usage

Run the pipeline:

```bash
python -m heckler
```

List audio devices (uses `sounddevice.query_devices()`):

```bash
python -m heckler --list-devices
```

The `pyproject.toml` console script entry point `heckler` also resolves to `heckler.pipeline:main`.

Logs append to `logs/heckler_YYYY-MM-DD.jsonl`. Startup progress lines prefixed with `[HECKLER]` go to stdout and are not written as JSONL events.

## First run

On the first launch you should expect **downloads**: Silero VAD weights via `torch.hub`, faster-whisper model files into the Hugging Face cache, and Kokoro assets when `Speaker` initializes. Subsequent starts reuse cached weights where possible.
