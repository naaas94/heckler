# pacing-before-llm — T2 — Pipeline pre-LLM pacing skip

## Chosen approach

- **`_run_reaction_worker`** calls **`pacing_gate.cooldown_status()`** before **`reactor_holder.get()`** / **`react()`**.
- When **`in_cooldown`**: log **`HeckleEvent`** with **`reactor_result=None`**, **`passed_score_gate=None`**, **`passed_pacing_gate=False`**, **`discard_reason=PACING_GATE`**, **`cooldown_remaining_at_eval`** from **`cooldown_status`**, **`llm_latency_ms=None`**, **`tts_latency_ms=None`**; **`context_buffer.push`**; **`continue`** — no **`react()`**, no **`on_reaction`**.
- When not in cooldown: existing path unchanged — **`react()`** → **`evaluate(score)`** → **`_execute_spoken_reply`** ( **`record_output()`** before **`speak()`** ) or error branches.

## Alternatives rejected

- **Pre-LLM `evaluate(score)` with a sentinel score:** rejected — violates Flag 1 / T1 contract; **`cooldown_status()`** is the score-free probe.
- **Firing `on_reaction` on pre-LLM pacing reject:** rejected — no **`ReactorResult`** (Flag 3 / gui-T1); post-LLM pacing reject still fires callback with **`was_spoken=False`**.

## Assumptions made

- **Single reaction worker** serializes utterances on one **`PacingGate`** — **`cooldown_status()`** at utterance start is consistent with post-LLM **`evaluate()`** after a multi-second **`react()`** on the same gate instance.
- **Flag 2 resolved:** pre-LLM rows omit **`reactor_result`** and do not set **`passed_score_gate=True`**.
- **`context_buffer.push`** on pre-LLM reject matches post-LLM pacing fail (plan A4).

## Items deferred

- **Controller `on_reaction` falsifiers:** **T3** — **`tests/test_controller.py`**.

## Files added

- **`tests/test_pipeline.py`** — **`test_reaction_worker_pre_llm_pacing_skips_react`**; **`_reaction_worker_pacing_mock`** for **`cooldown_status`** on reaction-worker tests (§2.2 / post-LLM tests must stay green).
- **Eval-strategy / README cohort note:** **T4**.
