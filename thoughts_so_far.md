- Echo (residual — re-validate after capture gate + tail + pre-LLM pacing):

    - **Transcripts sometimes repeat the last heckler line** — strong sign of **TTS → room/headphones → mic → ASR** (not a separate “generation channel” bug in the log format).
    - **Echo rows often mix with real speech** (e.g. user text + trailing heckler phrase in one segment).
    - **`tts_error` clustered at session start** — likely **startup/first-play** issues; later session mostly clean.
    - **Big timestamp gaps** mean **no qualifying segments** (silence, VAD not firing, or app not running) — not necessarily dropped logs.
    - **`semantic_density` can look “great” on echoes** — short, fluent sentences score high even when source is playback bleed.
    - **Latency spikes**: **first spoken line** very high **`tts_latency_ms`** (~1.7s) vs ~150ms steady state — **warmup/first synthesis** pattern; occasional **LLM multi‑second** spikes too.
    - **Scores cluster ~0.73–0.85**; rare lower **`absurdist`** passes (e.g. ~0.65).
    - **Mitigations still open**: headphones / routing / gain; **don’t call reactor when transcript ≈ last spoken comment**; optional **AEC** if you need speakers + mic.


- Context assembly or memory definition for this project
    - potentially some certified classics that replace the few-shot examples (early prompt/examples pass landed; no memory model yet)


- Memory operationally (how it’s used day to day, not just schema)


- Lower cooldown — use `pacing_interval` in persona TOML (e.g. `technician` @ 6s); default heckler still 12s


- Make logs more readable and rich (operator-facing; see also `gui_thougths.md`)


- Eval: SQLite events + `.dev/eval-strategy.md` landed; still need label workflow (`heckler_eval_labels` has no writer) and semantic surface analysis
