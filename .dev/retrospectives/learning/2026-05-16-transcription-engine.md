# Retrospective — learning · transcription-engine

**Date:** 2026-05-16  
**Task:** Heckler **transcribe-only mode** — SQLite transcript sessions/chunks, config + VAD overrides, `pipeline.main` mode split, CLI `--mode` / `--session-name`, markdown export, integration tests; plan **v1.1** with amendment **T6** (tracked plan tree, §8 repair, map baseline, decision-log supersession).  
**Why this qualifies:** Architectural-tier persistence and pipeline split, plus a **second-order** lesson: green implementation coexisted with an **invalid orchestrator handoff** until audit and T6 closed the object-graph gap. Worth compounding beyond the methodology file (`.dev/retrospectives/methodology/2026-05-16-transcription-engine.md`).

**Sources reviewed:** `.dev/plans/transcription-engine/plan.md`, `context-map.md`, `packets/T1.md`–`T6.md`, `.dev/audits/2026-05-16-transcription-engine.md` (rev 2 `pass`), `.dev/decision-logs/TE-T1.md`, `TE-T4.md`, `CHANGELOG.MD` (transcription-engine / T6 bullets), methodology retro above.

---

## 1. Task context

Shipped a **parallel pipeline path**: transcribe mode avoids constructing Reactor, Speaker, gates, and persona logging path; audio still flows through **AudioCapture** + **Transcriber.transcribe**; text lands in **new tables** via **`transcript_store`** sharing the configured SQLite **file** with events but **not** `HeckleEvent` or `SCHEMA_VERSION`. First “closure” claimed §8 complete while plan/packets/context were **outside git** or cited a **non-resolving tree SHA**; **T6** and audit rev **2** restored **§8.2** `git show HEAD:<path>` for the binding bundle and aligned the context map’s **Phase 0.5** baseline story.

---

## 2. What I now understand that I didn’t before

**Provenance is part of the product surface.** I used to think of “done” as merged code + pytest green. This arc separates **runtime correctness** from **binding resolvability**: if `.dev/plans/...` never hits `HEAD`, an auditor (or future you) cannot pin claims to blobs. The failure mode is **quiet** — nothing fails CI if you don’t run that gate — until someone runs `git show <SHA>:path`. I’ll remember: **handoff text that cites paths assumes those paths exist in the object database at the cited commit.**

**Reflexive SHAs beat pasted SHAs.** Plan §8.1’s move to “the id from `git log -1 --format=%H -- .dev/plans/transcription-engine/plan.md`” is not bureaucracy; it’s **self-healing documentation**. Any time I write a concrete tree hash in prose, I should ask whether it will still mean something after the next amend or cherry-pick.

**“Same SQLite file, different schema stories” is a design primitive I can name.** Transcript tables + `TRANSCRIPT_SCHEMA_VERSION` beside `event_store` + `heckler_schema_version` without FKs to `events` is not “messy duplication” — it’s **explicit parallel namespaces** (the plan’s Flag 1 resolution). That framing makes operational sense (one backup path) without entangling migrations.

**Frozen `HecklerConfig` + `dataclasses.replace` is the local pattern for mode-specific VAD.** I don’t need a mutable shadow config: a **derived** config instance for `AudioCapture` only keeps the mental model clean and avoids accidental mutation on the shared `HecklerConfig` reference.

**Mic gate without Speaker:** a **never-set `threading.Event()`** satisfies `is_playing`’s contract (“not playing” → don’t suppress the mic). That’s a small API-composition insight: the type is **`threading.Event`**, not **`Speaker`’s event`**.

**Scout-generated context maps age badly; “historical scout” must be first-class.** The jump from pre-implementation scout `7b5382e` to implementation HEAD was audit **P3** fuel. Maps that mix **navigation** with **stability** need a banner and a **single baseline commit** rule so Phase 0.5 diffs are not misread as “the map is wrong” when the map is **right for an old blob**.

**Cross-plan failure classes compound.** Persona-system audit **FIND-01** / **FIND-02** (stale map; stale “deferred” prose in decision logs) showed up again here. T6 explicitly ported that hygiene (`TE-T1` supersession banner). I now treat **FIND-02-class** as: *anything titled “deferred” that later ships must be edited or superseded*, not left as archaeological truth.

---

## 3. Decisions I made and would make again

**Separate module `transcript_store` instead of extending `event_store`.** Correct separation of migration policy and mental ownership; TE-T1’s rejected-alternatives table still reads right six months out.

**Skip lazy imports for Reactor/Speaker when construction-time loading is the real lever.** TE-T4’s rationale matches reality: import graph cost was not the bottleneck; **not constructing** heavy objects was enough, and tests can prove it with constructor stubs.

**Scoped `git add` for T6** (transcription-engine subtree + explicit files) rather than sweeping all `.dev/` noise — minimizes accidental policy fights and unrelated churn.

**Documenting deferrals in CHANGELOG + plan** for invalid env-only `HECKLER_MODE` (**F4** / **G1**) instead of pretending the gap doesn’t exist — keeps “waived with visibility” honest.

---

## 4. Decisions I made that I would change

**Calling §8 “Complete” on v1.0 without verifying every §8.2 path in the git object graph.** Underlying error: **conflating narrative closure with artifact closure**. Better rule: before any **Complete** banner, run the **§8.2 matrix** (or a script) on a **clean detached HEAD** at the claimed commit.

**Pinning a literal §8.1 SHA that didn’t contain the listed paths (P2).** Bad information + copy-paste. Better rule: **never** paste a completion SHA unless `git rev-parse` + `git cat-file -e` (or `git show`) was just run for **each** cited path.

**Leaving TE-T4’s header at “plan v1.0” after v1.1 (noted in methodology retro).** Small, but it violates the same “stale narrative” class FIND-02 targets; next time, **normalize headers** in the same remediation pass that touches adjacent logs.

---

## 5. Patterns in my own thinking

**Over-trusting “the implementation is merged.”** The repo’s *index* and *reachable trees* are part of the deliverable when using orchestrator §8 — I underweighted that until the audit.

**Under-tiering process-heavy subtasks:** T6 was labeled `standard` but carried the verdict hinge; in future I’d either **tier up** or explicitly tag “binding / provenance” in the packet title so staffing and review attention match blast radius.

**Motivated completion:** wanting a clean story in §8 without the friction of committing `.dev/plans/**` or re-running reflexive commands — the discomfort of T6-class work is **signal**, not annoyance.

---

## 6. Open questions

If **hybrid** “persona + transcript persistence in one process” ever ships, does **`init_schema` + `init_transcript_schema`** need a **documented ordering** or shared lock beyond today’s “transcribe path never calls `init_schema`” proof-by-construction?

Should **`HECKLER_MODE`** env validation match argparse’s choices **strictly**, or is “garbage in → persona default” an intentional operator footgun forever?

When audits stay **untracked** (§8.2 item 4 explicitly not asserted), what is the **lightweight** rule so audit text doesn’t diverge from the only copy in someone’s working tree?

---

## 7. Single paragraph synthesis

This task taught me that **a correct transcribe path in the working tree is insufficient** for a contract-first workflow: **binding artifacts must live in git at the handoff SHA**, and **context maps and decision logs need explicit supersession** when the scout baseline or “deferred” items are superseded by later work. On the technical side, the durable pattern is **parallel SQLite namespaces** with a dedicated store module, **`dataclasses.replace` for frozen config overrides**, and a **bare `threading.Event`** to satisfy the mic gate without Speaker — but the compounding insight is **treat `git show HEAD:path` as part of the definition of done** whenever the plan promises archaeology.
