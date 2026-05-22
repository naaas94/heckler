# Direction 1: Multi-Modal Persona System

## Status: Design — not yet implemented

## Summary

Heckler today is a single-personality system: dry deadpan commentator. The persona system turns heckler into a **skeleton** where the personality (system prompt, user prompt template, examples, config profile) is a swappable bundle. Swap the bundle and the system becomes something entirely different — rapid-fire Q&A, log engine, journal, didactical teacher, etc.

## Current Architecture (what we're changing from)

- **Single system prompt**: `prompts/system.md` — hardcoded path resolved in `Reactor.__init__` via `Path(__file__).resolve().parent.parent / "prompts" / "system.md"`.
- **Single examples file**: `prompts/examples.json` — same hardcoded resolution, pre-rendered into `self._examples_block` at init.
- **Fixed output schema**: `ReactorResult` with `comment`, `score`, `comment_type` (enum: sarcasm, deflation, observation, absurdist, passive_aggressive, callback, unknown).
- **Flat config**: `HecklerConfig` is a frozen dataclass with all tunables (LLM model, temperature, score threshold, pacing, voice, etc.) at the same level. No concept of profiles or overrides.
- **No persona selection**: no env var, no CLI flag, no runtime swap mechanism.

## Design Decisions

### TOML persona bundles

Each persona lives in its own directory under `prompts/`. A `persona.toml` file declares metadata and config overrides. System prompt and examples sit alongside it as sibling files.

```
prompts/
  heckler/
    system.md          # moved from prompts/system.md
    examples.json      # moved from prompts/examples.json
    persona.toml
  rapid-fire-qa/
    system.md
    examples.json
    persona.toml
  journal/
    system.md
    persona.toml       # no examples needed for all personas
```

Rationale: TOML is stdlib (`tomllib`, Python 3.11+ which is already our floor). A directory-per-persona keeps prompts co-located with their config. Adding a new persona is just adding a folder — no code changes.

### persona.toml shape

```toml
[persona]
name = "Heckler"
description = "Dry deadpan commentator"

[voice]
kokoro_voice = "af_sarah"
kokoro_speed = 1.05

[llm]
model = "openai/gpt-4o-mini"
temperature = 0.9
max_tokens = 150

[gates]
score_threshold = 0.65
pacing_interval = 12.0
density_threshold = 0.40
min_word_count = 4

[output]
comment_types = ["sarcasm", "deflation", "observation", "absurdist", "passive_aggressive", "callback"]
```

All sections except `[persona]` are optional — omitted fields fall back to `HecklerConfig` defaults. This means a minimal persona.toml is just:

```toml
[persona]
name = "My Persona"
description = "What it does"
```

### Config override merge

`HecklerConfig` stays frozen. A new function `apply_persona_overrides(base: HecklerConfig, persona: Persona) -> HecklerConfig` uses `dataclasses.replace()` to produce a new config instance with persona fields overlaid. The base config comes from `.env` / defaults as today; the persona narrows or widens specific tunables.

### Reactor refactor

`Reactor.__init__` currently hardcodes prompt paths. After refactor:
- Accepts `system_prompt: str` and `examples_block: str` (or a `Persona` object) as constructor arguments.
- No file I/O in `Reactor` — the caller (pipeline) is responsible for loading the persona and passing resolved content.
- This also makes `Reactor` easier to test (no filesystem dependency).

### CommentType handling

The `CommentType` enum is heckler-specific. Options considered:
1. Make enum open-ended — risk: loses type safety.
2. Per-persona validation — complex, premature.
3. **Keep enum but use `UNKNOWN` fallback for unrecognized types** — pragmatic, already exists.

Decision: option 3 for now. The `_parse_response` method in `Reactor` already handles `ValueError` on `CommentType(type_val)` — we change it to fall back to `UNKNOWN` instead of returning `None`. Per-persona response schemas are a later concern.

### Selection mechanism

- **Startup**: `HECKLER_PERSONA` env var or `--persona` CLI flag. Defaults to `"heckler"`.
- **Runtime (hot-swap)**: GUI sends a swap signal. The reaction worker processes one utterance at a time, so swapping the `Reactor` reference between iterations is GIL-safe (atomic reference assignment). No lock needed for the swap itself — just replace the reactor instance.

## GUI Surface — PyQt6

Decision: **PyQt6 minimal launcher**, not web-based. Rationale:
- Pipeline is threaded in-process Python — PyQt6 talks directly to pipeline objects, no serialization boundary.
- No browser dependency, no port management, no CORS.
- Persona swap is a method call on a controller, not an HTTP request.
- FastAPI backend deferred unless remote access / multi-client becomes a requirement.

The GUI for persona mode:
- Persona picker (dropdown or button row) — reads `list_personas()` on startup.
- Current persona description displayed.
- Live transcript feed (scrolling text area).
- LLM response feed (what heckler said back).
- Optional: config sliders for live tuning (temperature, score threshold, pacing).

## Implementation Plan

1. **Persona abstraction**: new `heckler/persona.py` — `Persona` dataclass, `load_persona(dir)`, `list_personas(root)`, `apply_persona_overrides(base, persona)`.
2. **Prompt migration**: move `prompts/system.md` and `prompts/examples.json` into `prompts/heckler/`, create `prompts/heckler/persona.toml`.
3. **Reactor refactor**: constructor takes `Persona` (or raw prompt strings), removes hardcoded path resolution.
4. **Config update**: add `persona_name: str = "heckler"` to `HecklerConfig`, add `HECKLER_PERSONA` to `load_config()`.
5. **Pipeline wiring**: load persona from config, apply overrides, pass to Reactor.
6. **Test updates**: tests that instantiate `Reactor` or reference `prompts/` paths need adjustment.
7. **PyQt6 GUI**: add dependency, build minimal launcher with persona picker and hot-swap.

## Open Questions

- Should persona bundles support custom response schemas (beyond comment/score/type)? Deferred — current JSON contract works for commentary-style personas. Revisit when a persona needs fundamentally different output.
- Should personas be installable from external packages / repos? Not now — local `prompts/` dir is sufficient.
- Voice per persona: Kokoro voice is already in config. Persona TOML can override it. But some personas might not want TTS at all (text-only output). Add an optional `[voice] enabled = false` flag later.
