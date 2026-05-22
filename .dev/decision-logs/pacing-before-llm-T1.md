# pacing-before-llm — T1 — `PacingGate.cooldown_status()`

## Chosen approach

- **`PacingGate.cooldown_status() -> tuple[bool, float]`** returns **`(in_cooldown, cooldown_remaining)`** using the same **`elapsed < min_output_interval_s`** and **`max(0.0, interval - elapsed)`** math as **`evaluate()`**, without reading **`score`** or **`score_override_threshold`**.
- **`_cooldown_state_locked()`** holds the shared snapshot; **`cooldown_status()`** and **`evaluate()`** both call it under **`self._lock`** so cooldown math is not duplicated and **`evaluate()`** does not double-acquire a non-reentrant lock.
- **`evaluate(score)`** behavior unchanged: not in cooldown → **`(True, 0.0)`**; in cooldown + score override → **`(True, cooldown_remaining)`**; else **`(False, cooldown_remaining)`**.

## Alternatives rejected

- **`evaluate(score=None)`** for a score-free probe: rejected — blurs analytics tri-state and couples pre-LLM pipeline to optional score; dedicated **`cooldown_status()`** is the plan contract (Flag 1 / §5.1).
- **`evaluate()` calling `cooldown_status()`** while both take **`threading.Lock`**: rejected — would deadlock; private **`_cooldown_state_locked()`** instead.

## Assumptions made

- **Flag 1 resolved (plan §0):** pre-LLM skip uses **`cooldown_status()`** only; **`score_override_threshold`** applies only on the post-**`react()`** **`evaluate(score)`** path (T2 wires pipeline).
- **Operators accept** no override during cooldown when the LLM is skipped (LLM cost savings over airing best lines without a score signal).

## Items deferred

- **Pipeline pre-LLM branch and `HeckleEvent` shape:** T2 — this subtask only adds the pacing API and unit tests.
- **Race between `cooldown_status()` and post-LLM `evaluate()` after a slow LLM:** accepted — single reaction worker serializes utterances (documented for T2).

## Files added

- **`tests/test_pacing_gate.py`** — **`cooldown_status`** cases plus override/evaluate divergence falsifier.
