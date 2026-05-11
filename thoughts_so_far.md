- from logs: 

    - **Transcripts sometimes repeat the last heckler line** — strong sign of **TTS → room/headphones → mic → ASR** (not a separate “generation channel” bug in the log format).
    - **`is_playing` only blocks capture during playback** — **tail/reverb/late bleed** after unmute can still become the next VAD segment and get transcribed.
    - **Echo rows often mix with real speech** (e.g. user text + trailing heckler phrase in one segment).
    - **`tts_error` clustered at session start** — likely **startup/first-play** issues; later session mostly clean.
    - **Big timestamp gaps** mean **no qualifying segments** (silence, VAD not firing, or app not running) — not necessarily dropped logs.
    - **Pacing usually blocks TTS on echo lines** (`pacing_gate`, few seconds cooldown left) — good for audio spam, but **reactor/LLM still ran** → **extra cost/latency**.
    - **`semantic_density` can look “great” on echoes** — short, fluent sentences score high even when source is playback bleed.
    - **Latency spikes**: **first spoken line** very high **`tts_latency_ms`** (~1.7s) vs ~150ms steady state — **warmup/first synthesis** pattern; occasional **LLM multi‑second** spikes too.
    - **Scores cluster ~0.73–0.85**; rare lower **`absurdist`** passes (e.g. ~0.65).
    - **Mitigations to remember**: headphones / routing / gain; **extend mute after playback**; **don’t call reactor when transcript ≈ last spoken comment**; optional **AEC** if you need speakers + mic.
    - **Evening session** in the log looked **cleaner** (less echo pattern) — setup or behavior changed between runs.


- **Pacing gate (validated in code):** In `heckler/pipeline.py` `_run_reaction_worker`, `pacing_gate.evaluate()` runs **after** `reactor.react()` succeeds. So pacing **does not block the LLM**; it only blocks **`_execute_spoken_reply` / TTS** (and `record_output()` still fires immediately before `speaker.speak()` per `pacing_gate.py`). Moving pacing before the LLM would be a deliberate behavior/cost change (e.g. need another signal for score-override or accept dropping that path).

- gotta look into context assembly or memory definition for this proj
    - potentially some certified classics that replace the few shot examples 


- I know I said already to look into memory but also look inot memory operationally wise 


- lower the cooldown


- make logs more readable and rich 

- analytics and eval missing


- gotta look into analytics and semantic surface analysis 


- init cli 

- since this can be open and transcribing at all times it could lead to some interesting log system or build up- keeping it in mind


- it could be cool to have an interface to tune the persona, style, responses, etc. As in literally toggles or buttons for characters (peter grifin, snob old english lady, etc), and traits (ironic, acid, roast, etc) so that we can switch and combine ad hoc at the interface surface level (gui): to continue polishing. 

- this could actually be useful for quick shot questions 
    - and even interview support 

- for prompt engineering insights and nuggets; go back to roast session conv w claude and extract from there

