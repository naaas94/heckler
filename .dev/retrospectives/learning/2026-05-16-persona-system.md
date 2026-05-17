# Learning retrospective — persona-system

**Date:** 2026-05-16  
**Sources:** `.dev/plans/persona-system/plan.md` (v1.1), `context-map.md`, executor packets `T1.md`–`T7.md`, `.dev/audits/2026-05-16-persona-system.md` (through revision 3), `.dev/decision-logs/persona-system-T1.md`, `persona-system-T3.md`, `.dev/decision-logs/T7.md` (reactor), `.dev/persona-system.md` (design prose).

---

## 1. Task context

**What shipped:** A swappable persona layer for Heckler — directory bundles under `prompts/<name>/` with `persona.toml`, moved default assets to `prompts/heckler/`, new `heckler/persona.py` (load/list/apply overrides), `HecklerConfig.persona_name` + `HECKLER_PERSONA`, pipeline wiring + `--persona`, and a reactor refactor so `Reactor` takes caller-resolved prompt text instead of hardcoded paths, plus `_parse_response` falling back to `CommentType.UNKNOWN` instead of returning `None`.

**Why this earns a learning retrospective (not just methodology):** The work was explicitly **architectural** in places (persona module + reactor seam), used **contract-first decomposition** with parallel executor lanes, then exposed a **second-order failure mode**: implementation and tests could be green while **planning archaeology** (context map baseline, deferred bullets in decision logs, packet vs repo tree) failed audit — and a **third-order** gap appeared when the remediation packet file existed on disk but not in `HEAD` (**FIND-ARCH-1** in audit rev 3). That stack — code correct, docs “complete,” git object graph wrong — is worth remembering.

---

## 2. What I now understand that I didn’t before

**Context maps have a lifecycle, not a truth bit.** A map generated at commit *A* is not “wrong” when implementation later changes those paths; it is **stale relative to a chosen baseline**, which is **expected** after land. The useful artifact is the **method**: for each §File map row, `git diff --quiet <map_sha> HEAD -- <path>` — and language in the plan intake that does not underplay that rule (FIND-01 in the v1.0 → v1.1 arc). I had been mentally treating “stale map” as a moral failure of the scout; it is closer to **version skew between two intentional moving parts** (tree vs narrative).

**Binding surfaces beat design essays.** The plan’s §2 mapping table (e.g. `pacing_interval` → `min_output_interval_s`) explicitly told executors to prefer the table over `.dev/persona-system.md` prose. That pattern worked: naming collisions between TOML ergonomics and frozen `HecklerConfig` fields did not become merge thrash. The design doc’s header still read “not yet implemented” while code shipped — a reminder that **informational** docs rot unless someone owns a cheap “status line” pass.

**“Deferred until T5” rots into false history.** The reactor decision log (`persona-system-T3.md`) kept “Items deferred” bullets that described the world *before* pipeline wiring landed; after T5, those bullets **read as current** to a cold auditor (FIND-02). Supersession banners and a **Landed** section are not ceremony; they are **anti-confabulation guards** when multiple agents and phases read the same file at different times.

**Parallel subtasks with a frozen contract actually worked.** Persona module (new file), prompt migration, reactor signature change, and config field were scheduled parallel with T5 as the integration choke point. The plan explicitly allowed the reactor work to code against §2 without waiting for the persona module to exist in-tree — **the contract was the synchronization primitive**, not the branch order. That is a reusable pattern when file ownership is disjoint and interfaces are small.

**Audit verdict `fail` on green tests is a valid outcome class.** Revision 2’s blocking findings were documentation and traceability, not behavior. Internalizing that prevents the gut reaction of “the auditor is being pedantic” when the real risk is **merge archaeology** and onboarding cost.

**Declared artifact matrices need a `git` falsifier.** Revision 3’s FIND-ARCH-1: `packets/T7.md` listed in plan §6 / §8 as tracked, present on disk, **absent from `HEAD`**. The lesson is mechanical: before calling a plan “complete,” run the same check the auditor runs — `git show HEAD:<path>` or `git ls-files` — not only “file exists in the editor tree.”

---

## 3. Decisions I made and would make again

- **§2 as the single binding contract** (types, mapping table, log strings, test names) — it bounded executor creativity without a single mega-PR.
- **Splitting prompt filesystem concerns out of `Reactor`** — pushes persona policy to pipeline + `persona.py`, keeps the LLM shell testable with injected strings.
- **UNKNOWN fallback instead of `None`** for bad `type` strings — trades silent discard for explicit, gated behavior; aligns with “say something weird” vs “pretend the model failed” product intuition when scores are high.
- **T7 as docs-only audit remediation** — kept runtime risk zero while cleaning FIND-01–03; correct separation when the audit does not file code defects.

---

## 4. Decisions I made that I would change

- **Treating “packet emitted” as done without verifying git tracking** — led to FIND-ARCH-1. Better rule: any path named in §8’s artifact chain must resolve in **`HEAD`** before the handoff checkbox gets ticked, or the plan must say “optional / local only” explicitly.
- **Leaving stale evidence parentheticals in §5.4** (e.g. old `Reactor(config)` cite) after the seam moved — low harm but trains readers to distrust the adversarial section. When coupling is “resolved,” update or strike the example line.
- **Letting `.dev/persona-system.md` status drift** — either bump the status line when the plan closes, or add one sentence pointing at the plan as normative; otherwise new readers anchor on the wrong timeline.

**Underlying error:** conflating *narrative closure* (words in markdown) with *repository closure* (objects reachable from `HEAD`).

---

## 5. Patterns in my own thinking

- **Comfort with parallel execution** rose during this task — good — but **comfort with the artifact graph** did not rise equally — that asymmetry produced FIND-ARCH-1.
- **Auditor as adversary vs auditor as linter:** early reflex might be defensiveness on FIND-01/02; the more useful frame is the auditor as **forcing function for time-indexed truth** in a multi-phase repo.
- Watch for **sunk cost in “the plan is already very detailed”** — detail did not prevent a one-file git slip; the checklist layer still matters.

---

## 6. Open questions

- **`_flatten_persona_toml` passthrough:** Unmapped keys in known sections keep TOML-local names; if a future key accidentally matches a `HecklerConfig` field name, `apply_persona_overrides` could apply it without the “unknown key” WARNING path. Is a stricter allowlist worth it, or is convention enough?
- **`[output]` beyond `comment_types`:** Only `comment_types` is explicitly skipped; other keys may pass through — intentional flexibility or future footgun?
- **Cross-plan concurrency:** Transcription-engine work added mode flags and early-return paths; persona loading stayed correctly ordered *today* — worth a periodic re-scan when new `main()` branches appear.
- **Design doc vs shipped:** Should `.dev/persona-system.md` be updated to “implemented” with a pointer to §2, or left as historical design? (Product/documentation choice, not code.)

---

## 7. Single paragraph synthesis

Persona-system taught that **contract-first parallel execution can ship clean code and green tests while still failing the real gate — traceability of planning artifacts to the git object graph and to time-indexed truth** (context map baselines, superseded deferred prose, and files that exist in the worktree but not in `HEAD`). The compounding move is to treat **HEAD-reachability and per-row baseline checks** as part of “done,” not as audit-only pedantry, and to use **explicit supersession and Landed sections** wherever a document’s earlier bullets would otherwise masquerade as current system facts.

---

## Cross-links (for future you)

- Methodology twin (process audit): `.dev/retrospectives/methodology/2026-05-16-persona-system.md` (companion discipline).
- Audit revisions: `.dev/audits/2026-05-16-persona-system.md` (FIND-01–03 closed; FIND-ARCH-1 open at last read — resolve by committing `packets/T7.md` when you want a clean merge verdict).
