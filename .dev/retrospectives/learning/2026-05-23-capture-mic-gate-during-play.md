# Retrospective — learning · capture-mic-gate-during-play

**Date:** 2026-05-23  
**Task:** Capture-layer **Rule 1** — while `Speaker.is_playing` is set (synthesis, blocking playback, `tts_gate_tail_ms` tail), `AudioCapture` must not form Silero VAD segments; discard in-progress capture; reset `VADIterator` on unmute; keep `_emit_audio_segment` enqueue skip as second defense. Plan **v1.0** (`T1` implementation + tests + decision log → `T2` docs + tracked plan bundle).  
**Why this qualifies:** Architectural-tier change to the real-time audio path, explicit supersession of a prior plan’s load-bearing assumption, and a failure mode that only makes sense once you see **stateful upstream buffering** vs **downstream side-effect gating**. Process closure repeated the transcription-engine §8 lesson; the domain lesson is distinct and worth compounding.

**Sources reviewed:** `.dev/plans/capture-mic-gate-during-play/plan.md`, `context-map.md`, `packets/T1.md` / `T2.md`, `.dev/decision-logs/capture-mic-gate-during-play-T1.md`, `.dev/decision-logs/tts-mic-gate-tail-T2.md` (supersession), `.dev/audits/2026-05-22-capture-mic-gate-during-play.md`, `.dev/retrospectives/methodology/2026-05-23-capture-mic-gate-during-play.md`, `CHANGELOG.MD`, `heckler/audio_capture.py`, `tests/test_audio_capture.py`, `heckler/speaker.py`, `heckler_seed.md` (§4.1 / §4.7 / Coupling Surface 2), `thoughts_so_far.md`, `git log` for `da8aca82` / `504ca113` / `bb7746aa`.

**Companion:** Process audit — `.dev/retrospectives/methodology/2026-05-23-capture-mic-gate-during-play.md` (§8 closure, F-001, handoff SHA). This file is **what the mic gate taught about audio pipelines and layered fixes**, not executor discipline.

---

## 1. Task context

**What shipped (code at `da8aca82`, docs/plan bundle at `504ca113`, §8 remediation at `bb7746aa`):**

- Module-level **`play_gate_frame_tick`** + frozen **`PlayGateFrameResult`** — pure state machine for per-frame play-gate behavior (testable without Silero).
- **`AudioCapture._capture_loop`** — calls tick each 512-sample frame; **`continue`** before `vad_iter` while `is_playing`; **`new_vad_iterator()`** when `reset_vad` after a gated period; max-speech flush discards instead of emitting if gate is set (defense in depth).
- **`_emit_audio_segment`** — unchanged early return when `is_playing.is_set()` (second defense; tests retained).
- Docs: `heckler_seed.md` Rule 1 + Rule 2 language, `README.md`, `CHANGELOG.MD`, supersession banner on tail-plan decision log.
- **No** changes to `Speaker`, `controller.py`, `pacing_gate.py`, or reactor order.

**Symptom being fixed:** After a spoken heckle, logs showed **transcript ≈ last `reactor_result.comment`** — the mic had **recorded TTS/bleed during play**, then **flushed a VAD segment when the gate cleared**, so Whisper + reactor treated the echo as new user speech. Extending **`tts_gate_tail_ms`** (prior plan) lengthened the mute window but did not stop Silero from **accumulating** audio in `capturing` / `segment` while the event was still set.

**Why a learning retrospective (not only methodology):** The fix is a small diff with a large conceptual footprint — **where** a gate must live in a pipeline with **stateful iterators** and **cross-thread Events**, and how that interacts with a **separate** plan (`pacing-before-llm`) that addresses the same *symptom* at a different layer. That’s stack + product reasoning, not just “did T2 commit the plan bundle.”

---

## 2. What I now understand that I didn’t before

### Gates belong where state accumulates, not where side effects fire

Before this task I treated “mic gate” as **“don’t enqueue `AudioChunk`”** — which was already implemented in `_emit_audio_segment`. The validated failure mode from the context map and `thoughts_so_far.md` is **buffer-then-emit**: `_capture_loop` kept calling `vad_iter`, honoring `"start"` / `"end"`, and growing `segment` **while** `is_playing` was set; `_emit_audio_segment` never ran until silence closed the segment, often **after** `is_playing.clear()`. The gate at enqueue was **too late** — like checking permissions only at `INSERT` while the ORM session already built a toxic object graph.

General rule I want to reuse: **find the mutable state that crosses the forbidden window** (here: `capturing`, `segment`, `VADIterator` internals, and drained PCM fed into Silero). Put the gate **before** that state advances, not only before the irreversible side effect (queue put).

### Two complementary plans for one symptom: time window vs. listening behavior

The **`tts-mic-gate-tail`** plan was correct for its slice: **digital playback ends before acoustic energy in the room does**, so `Speaker.speak` should hold `is_playing` for `tts_gate_tail_ms` after `sd.play` returns. That plan explicitly assumed capture could stay emit-only. **`capture-mic-gate-during-play`** superseded that assumption without invalidating the tail — **tail controls how long Rule 1 applies**; **Rule 1 controls what capture does while the Event is set**.

Naming this in `heckler_seed.md` as **Rule 1 (capture loop)** vs **Rule 2 (pacing / pre-LLM)** helps when debugging “echo” in logs:

| Layer | Mechanism | What it prevents |
|-------|-----------|------------------|
| Rule 1 | No VAD segments while `is_playing` | Echo **audio** entering the transcript pipeline |
| Tail | Extended `is_playing` after digital play ends | Late **room** bleed before unmute |
| Rule 2 | `PacingGate.cooldown_status()` before `react()` | **LLM cost** on lines that still slip through (e.g. post-tail bleed) |
| Emit guard | `_emit_audio_segment` early return | Enqueue if loop ever regresses |

I had been conflating “echo” with a single knob. In practice **`thoughts_so_far.md` already separated** pacing blocking TTS vs. reactor still running — capture-first was the right ship order because **stopping bad audio is cheaper than scoring bad text**.

### Stateful iterators need an explicit “mode transition” reset

Silero’s `VADIterator` is not a pure function of the current frame — it carries internal state across calls. Clearing `segment` without resetting `vad_iter` (Surface 3 in the context map) risks **spurious `start`/`end` immediately after unmute**. The plan’s **`was_gated` + `reset_vad` on first open frame** is a reusable pattern: **when a long-lived iterator is frozen by an external gate, rebuild it on resume**, don’t assume zeroed buffers are enough.

The pure helper makes that edge explicit:

```29:55:heckler/audio_capture.py
def play_gate_frame_tick(
    is_playing: bool,
    was_gated: bool,
    capturing: bool,
    segment: list[np.ndarray],
) -> PlayGateFrameResult:
    ...
    if was_gated:
        return PlayGateFrameResult(
            capturing=capturing,
            segment=segment,
            was_gated=False,
            reset_vad=True,
        )
```

Loop integration then does `vad_iter = new_vad_iterator()` when `tick.reset_vad` — separation of **policy** (tick) from **IO** (hub-loaded model) is what made CI falsifiers possible.

### PCM deque backlog is a second buffer to reason about

Surface 5: `_vad_callback` keeps appending to `_pcm` while the loop is gated. The fix is **not** “stop the callback” (it must stay fast) but **drain each iteration and drop frames on the floor** via `continue` before `vad_iter`. If I had only skipped `vad_iter` without draining, post-unmute would process a **burst of stale frames** including bleed. “Discard while gated” means **consume and ignore**, not **pause ingestion**.

### Product tradeoff: discard whole overlapping segment (Flag 2)

When play starts mid-utterance, the plan chose **drop the entire partial segment**, not “emit user-only prefix when gate clears.” That aligns with Rule 1 literally: **if it’s playing, don’t listen** — including to user speech that overlaps TTS. Barge-in during synthesis, playback, or tail remains impossible because **`Speaker` and `AudioCapture` share one Event**; tuning `TTS_GATE_TAIL_MS` is the operator valve, not capture splitting segments. I should recognize this as an intentional **UX/security-of-heckle** tradeoff, not a missing feature, unless product later demands barge-in (which would need a different signal than `is_playing` alone).

### Extract a pure tick when integration tests are rightly forbidden

Flag 3 forced a design I’d been avoiding elsewhere: **no default pytest that calls `torch.hub.load`**. The honest contract is:

- **Proven:** `play_gate_frame_tick` semantics (3 tests).
- **Proven:** emit path still skips when playing (existing tests).
- **Not proven in CI:** `_capture_loop` wiring under toggling `Event` + real Silero.

That’s a **deliberate hollow** — audit F-003/F-005 — not accidental untested code. The learning is: **document which layer of the stack each test certifies**, and accept that loop wiring regressions require manual persona runs or a future opt-in integration job. A middle ground I didn’t take: a tiny loop stub that mocks `vad_iter` without hub — still more coupling than the helper-only approach.

### `threading.Event` as shared boolean across threads — and the narrow race

`Speaker` sets/clears `is_playing` from the reaction/TTS thread; `_capture_loop` reads it every frame. The implementation calls `is_set()` twice per frame (inside `play_gate_frame_tick` and again for `continue`). Audit **A-3 / F-006**: if clear happens between those calls, one frame might hit `vad_iter` before `was_gated` drives `reset_vad` on the **next** frame. Mitigation is “next frame fixes it,” not proof of impossibility. For Heckler’s coarse 512-sample frames (~32 ms), that’s acceptable; for tighter latency I’d pass a single snapshot `playing = self._is_playing.is_set()` per frame.

Transcribe mode’s **never-set `Event()`** remains the proof that the gate API is **“optional suppressor”** composition, not a hard `Speaker` dependency — same lesson as transcription-engine learning notes.

### Semantic gate can lie on echo text

`thoughts_so_far.md` noted **high `semantic_density` on echo lines** — fluent, short, on-topic. Capture-first fixes the **root audio path**; pacing fixes **cost**. I won’t expect lexical gating alone to catch playback bleed.

---

## 3. Decisions I made and would make again

**Capture-first before `pacing-before-llm` (Flag 5 resolution).** Stopping segment formation removes bad chunks from the queue; pre-LLM cooldown only helps after something was already transcribed. Same symptom, different layer — sequencing was correct.

**Pure `play_gate_frame_tick` + keep emit guard.** Defense in depth is cheap here; removing emit skip would shrink the regression surface in tests without meaningfully simplifying the loop.

**Discard whole segment on gate (Flag 2).** Matches Rule 1 wording and avoids echo tails in concatenated numpy arrays; splitting user vs. bleed without AEC would be guesswork.

**Explicit supersession in `tts-mic-gate-tail-T2.md` rather than silent rewrite.** Future readers see *why* tail shipped first and what failed — avoids “we fixed capture twice” confusion.

**Reject Speaker-only and emit-only decompositions (plan §5.1).** Adversarial pass was load-bearing; both were plausible “smaller diffs” that don’t touch the accumulating state.

**No new config for capture behavior.** Gate duration stays in `TTS_GATE_TAIL_MS` on the Speaker side; capture only **reacts** to `Event` — single choke point for “how long is gated.”

---

## 4. Decisions I made that I would change

**Trusting “emit gate = mic gate” in docs and mental model for too long after tail shipped.** The tail plan’s decision log assumption (“capture changes unnecessary”) was reasonable at T2 time but became false once buffer-then-emit was traced in logs. Better rule: after any gate extension, **re-validate the consumer’s state machine**, not only the producer’s hold duration.

**Calling plan work complete before `git show <handoff>:plan.md` contained §8** (F-001 — same class as transcription-engine). Implementation was right; **closure narrative** was ahead of the object graph until `bb7746aa`. I would run the §8.2 matrix on the commit I’m about to cite **before** `Status: Complete`, or cite **`bb7746aa`** as `closure_sha` distinct from **`504ca113`** `implementation_sha`.

**Megacommit bundling capture §8 with pacing §8, audits, archives, transcripts.** Velocity-friendly, weak for per-plan archaeology — prefer a single-purpose “plan §8 only” commit when fixing F-001 (methodology retro already says this; I’d actually do it next time).

**Not scheduling audit rev 2 after F-001 fix.** Condition was met in git; audit file still says `pass-with-conditions` with open F-001 — understates final state for future readers.

**Optional: snapshot `is_playing` once per frame** to shrink A-3 window — low cost, not done; I’d add it if barge-in or shorter frames ever matter.

---

## 5. Patterns in my own thinking

**Fixing symptoms at the last responsible layer.** Tail plan extended *when* the gate opens; I initially underweighted *what capture did while closed*. Familiar pattern: patch where logs show pain (enqueue) instead of where state diverges (VAD loop).

**Over-confidence from green emit tests.** `test_emit_skips_when_speaker_is_playing` documented only the second defense; it **passed throughout** the bug era. Tests that certify layer N must not be read as certifying layer N−1.

**Trusting executor “complete” without artifact grep.** T2 message said plan bundle tracked; §8 still read “Not produced” in `504ca113` — I wanted the story closed. Discomfort running `git show` on every §8.2 path is signal (also in persona-system / transcription-engine arcs).

**Under-splitting “echo” in diagnosis.** I knew pacing could block TTS; I didn’t always separate **audio echo** (capture) from **LLM echo** (reactor ran on bad transcript). The context map’s forward/reverse import graphs helped; I should start from **coupling surfaces** earlier when symptoms are cross-module.

**Reasonable supersession vs. plan churn.** Two plans in two days (`tts-mic-gate-tail` → `capture-mic-gate-during-play`) could feel like thrashing; it was **assumption revision with evidence**, not scope creep — worth internalizing so I don’t resist supersession banners in decision logs.

---

## 6. Open questions

**Manual validation matrix:** What’s the minimal repeatable persona run (mic placement, `TTS_GATE_TAIL_MS` values) that falsifies buffer-then-emit on hardware without Silero in CI? Worth a short operator checklist in personal notes, not necessarily repo docs.

**Barge-in:** If product ever wants interrupt-during-TTS, is a second Event or priority channel required, or is shortening tail + headphones enough?

**Helper vs. loop drift:** Would a **five-line** test that monkeypatches `_capture_loop`’s inner loop body (no hub) to assert `vad_iter` is not called when `playing.set()` pay for itself, or is that false confidence?

**Hybrid modes:** If persona + transcript persistence merge paths, does shared `is_playing` wiring stay one Event per `AudioCapture` instance?

**Cross-plan meta:** When audit cites `implementation_sha` vs `closure_sha`, should learning retros always record both so six-month reads don’t chase the wrong commit?

---

## 7. Single paragraph synthesis

This task taught me that **a mic gate implemented only at enqueue cannot protect a stateful capture loop** — Silero will buffer bleed during `is_playing`, then flush echo when the gate clears — and that **fixing “echo” in a heckler stack is inherently layered**: tail duration (how long not to listen), capture Rule 1 (don’t form segments while gated), pacing Rule 2 (don’t pay for LLM on what still slips through). The durable engineering move was **`play_gate_frame_tick`**: separate pure policy from hub-bound integration, reset the iterator on gate clear, drain-and-drop PCM while gated, and supersede the prior plan’s assumption in writing. The recurring personal mistake was **confusing pytest-green emit tests with a gated capture path** and **marking orchestrator plans complete before §8 exists in git** — the code for Rule 1 is landed; the compounding habit is to trace **mutable state** and **artifact SHAs** with the same rigor as the Event semantics.
