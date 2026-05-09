# Audit — litellm-provider-switch

## 1. Audit metadata

| Field | Value |
|--------|--------|
| **Task name** | litellm-provider-switch |
| **Plan document** | `.dev/plans/litellm-provider-switch/plan.md` **v1.1** |
| **Audit date** | 2026-05-09 |
| **Repository HEAD** | `1788bf89fe81e97999ec4fb5ff87ac1f6c14a556` |
| **Context map path** | `.dev/plans/litellm-provider-switch/context-map.md` |
| **Readiness verdict (map)** | CONDITIONAL |
| **Auditor focus (Phase 4)** | **Integration seams** (plan §5.4 couplings; composer correctness for `litellm.completion` + `_litellm_auth_params`). **Failure paths** (exception envelope, empty/malformed completion shapes). **Regression surface** (pipeline test `HecklerConfig` construction; CLI unchanged). Rationale: highest plan risk is T2/T3 seam + auth kwargs; second is error/normalization paths already partially tested. |

**Integration seams waiver:** Not applied — plan §5.4 lists multiple confirmed couplings; integration focus was exercised.

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|--------|--------|
| **Context map path** | `.dev/plans/litellm-provider-switch/context-map.md` |
| **Map provenance SHA** | **unavailable (no `.git` at exploration time)** — no per-file staleness diff vs scout baseline. |
| **Plan §0 post-execution SHA (v1.1)** | `1788bf89fe81e97999ec4fb5ff87ac1f6c14a556` |
| **SHA comparison** | **match** — current `git rev-parse HEAD` equals plan-recorded post-execution SHA. |
| **Working tree at audit** | **dirty** — `.dev/plans/litellm-provider-switch/plan.md` modified (not listed in context map §File map). No `dirty-state caveat` on scout-flagged code paths from this edit. |
| **Context map absence** | **none** — map present for a task that touched existing code. |

**Scout grep coverage check (vs plan §5.4 / operator vocabulary implied by §2):** Context map §Coupling surfaces recorded greps for `anthropic_api_key`, `ANTHROPIC_API_KEY`, `Anthropic` / `messages.create`, `llm_model` / `claude-haiku`, `prompts/`, `.dev/decision-logs`. Patterns aligned with pre-migration reality. **Not recorded pre-scope:** `HECKLER_LLM_MODEL`, `OPENAI_API_KEY`, `litellm`, `OPENAI`-style keys — appropriate for a map drawn before migration; filed as **scout-incomplete** (minor, feedback to pre-plan-exploration), not as a code defect.

**Phase 0.5 findings filed here:** none of type `context-map-stale` (no mappable file-level SHA in map header). `scout-incomplete` — see finding **S1** in findings table.

---

## 3. Context chain completeness

| Artifact | Status | Notes |
|-----------|--------|--------|
| Context map | **provided** | CONDITIONAL; SHA unavailable at scout time. |
| Orchestrator plan | **provided** | `plan.md` v1.1 |
| Subtask packets T1–T4 | **provided** (paths exist under `packets/`) | Not line-for-line replayed in this report; contracts taken from `plan.md`. |
| Decision logs T10, T11 | **provided** | |
| Decision logs T7, T9 (errata) | **provided** | |
| Changelog | **provided** | `CHANGELOG.MD` |
| Codebase / tests | **inspected** | `heckler/config.py`, `heckler/reactor.py`, `pyproject.toml`, `tests/test_models.py`, `tests/test_reactor.py`, `tests/test_pipeline.py`, `heckler/pipeline.py`, `.env.example`, `README.md`; spot-check `heckler_seed.md`. |
| **Phase 0 narrative isolation** | **partial** | Full plan and context map were loaded during artifact discovery before cold-read pinning (ordering deviation from strict auditor Phase 0). **Cold-read findings** were still composed primarily from code + §2 contracts + tests; narrative conflict checks appear in Phase 1 / Phase 3. |

---

## 4. Cold-read log (Phase 0 — pinned)

**Inputs honored for substance:** task statement (plan §1), shared contracts (plan §2), implementation files, tests. *(Strict isolation from plan prose beyond §1/§2 was not maintained — see §3.)*

| ID | Finding | Severity (guess) |
|----|---------|------------------|
| C1 | `Reactor.react` imports `litellm` inside the method — reduces import-time side effects (addresses suspected coupling in plan §5.4). | observation |
| C2 | `completion_assistant_text` is public and handles `str` and list-shaped `message.content` — centralizes extraction for tests. | observation |
| C3 | `_litellm_auth_params` maps `openai/` and **`azure/`** to `openai_api_key`, `anthropic/` → key, `ollama/` → `api_base`, bare model id → `openai_api_key` if set — **Azure branch is an extension** relative to minimal §2 table (plan §8.3 flags this). | risk / minor drift vs shortest §2 wording |
| C4 | `load_config` uses `getenv` with defaults for LLM keys; `HECKLER_LLM_MODEL` strip with whitespace fallback — matches optional-key story. | observation |
| C5 | `pyproject.toml` lists `litellm`, no `anthropic` — consistent with migration narrative. | observation |
| C6 | `_parse_response` still uses `_JSON_OBJECT_RE = r'\{[^}]+\}'` — cannot extract nested JSON objects; pre-existing limitation if model returns nested structure. | minor risk (legacy) |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|-----------|------|-------|---------|-------------|
| **F1** | **major** | contract-violation | 1, 3 | **T4** | `.dev/decision-logs/T7.md` and `T9.md` **main “Chosen approach” sections still state Anthropic-only reactor/pipeline wiring** (and T7 wrong 2-tuple score-gate shape; T9 `messages.create` wrapper narrative). Plan **§4 T4 kill criterion** requires not leaving logs asserting false **current** behavior; **Landed** errata does not remove or clearly fence the obsolete body. |
| **F2** | minor | decision-log-stale | 3 | T7 | **Landed** errata updates LLM backend but **“Chosen approach”** still says score gate returns `(None, latency)` without `DiscardReason` — contradicts shipped `react` contract and T7 Landed bullet. |
| **F3** | minor | drift | 2, 3 | T2 / T11 | `_litellm_auth_params` treats **`azure/`** like **`openai/`** for `api_key`; **T11** documents `openai/`, `anthropic/`, `ollama/`, bare id — **Azure** not named (plan §8.3 notes possible extension). |
| **S1** | minor | scout-incomplete | 0.5 | — | Scout grep set did not include post-migration env keys / `litellm` tokens; predictable for pre-migration map — feedback for pre-plan-exploration iteration. |
| **O1** | observation | — | 4 | — | `tests/test_pipeline.py` still uses `HecklerConfig(anthropic_api_key="test-key")` — **confirmed** coupling from plan §5.4 remains valid (field retained). |
| **O2** | observation | — | 4 | — | Lazy `litellm` import in `react` — **suspected** “import side effects” coupling **ruled out** for module import; first call still loads `litellm`. |

No **critical** findings identified (no evidence of security flaw or silent intent violation in core contracts).

---

## 6. Detailed findings (above minor severity)

### F1 — T4 kill criterion vs decision-log body (major)

**Expected:** Per plan §4 **T4**, decision logs must **not** leave assertions that describe **false current** reactor/pipeline behavior after errata; obsolete narrative should be struck, fenced as historical, or replaced so a reader cannot mistake it for today’s code.

**Found:**

- **`T7.md`** — “Chosen approach” still describes **`Anthropic(api_key=...).messages.create()`** and score gate as **`(None, latency)`** only (lines 6–9).
- **`T9.md`** — “Chosen approach” still describes **`Reactor` (Anthropic)**, **`_react_with_discard`**, and **`reactor._client.messages.create`** wrapping (lines 5–8).

**Landed** sections correctly describe LiteLLM and direct `reactor.react`; they do **not** negate the misleading **Chosen approach** blocks for a reader who scans from the top.

**Evidence:** `.dev/decision-logs/T7.md`, `.dev/decision-logs/T9.md`; plan §4 T4 kill criteria; plan §5.4 Surface 7.

---

### F2 — T7 score-gate tuple in historical section (minor)

**Expected:** Decision text should not contradict **Landed** errata or §2 `react` return type.

**Found:** `T7.md` line 8 still states score gate returns **`(None, latency)`** without **`DiscardReason.SCORE_GATE`** — stale vs current `tuple[..., Optional[DiscardReason]]` contract.

---

### F3 — Azure branch undocumented in T11 (minor)

**Expected:** Shared contracts + T11 describe provider routing; extensions should appear in T11 if intentional.

**Found:** `heckler/reactor.py` `_litellm_auth_params` includes **`provider in ("openai", "azure")`** sharing **`openai_api_key`**. **T11** lists **`openai/`**, **`anthropic/`**, **`ollama/`**, bare id — not **`azure/`**. Plan §8.3 flags Azure as a possible extension — acceptable if docs/README mention Azure for operators; README table does not list Azure explicitly (operators may still set `HECKLER_LLM_MODEL=azure/...` per LiteLLM). Residual **drift** between decision log and code.

---

## 7. Adversarial test log (Phase 4)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| **§5.4 — Pipeline test constructs `HecklerConfig(anthropic_api_key=...)`** | Still valid if field exists | `tests/test_pipeline.py` uses field; pipeline runs with mock `Reactor` | **passes** |
| **§5.4 — litellm import side effects on `import heckler.reactor`** | No network at import if lazy | `litellm` imported inside `react` only | **passes** (import path) |
| **`litellm.completion` failure** | ERROR log provider-agnostic; `(None, latency, LLM_ERROR)` | `except Exception` → `logger.error("LLM API call failed: %s", exc)` → `DiscardReason.LLM_ERROR` | **passes** |
| **Empty `choices` / `None` response** | Parse failure → `LLM_ERROR` | `completion_assistant_text` → `""` → `_parse_response` → `None` → `LLM_ERROR` | **passes** (see `tests/test_reactor.py`) |
| **`completion_assistant_text` list parts** | JSON preserved | Test `test_completion_assistant_text_joins_list_text_parts` | **passes** |
| **§5.4 Surface 6 — Anthropic blocks vs OpenAI choices** | Normalized via helper | `completion_assistant_text` + tests | **passes** |
| **`azure/` model id auth** | Uses OpenAI key path when set | Code branch present; **no dedicated test** | **unknown** (low priority; LiteLLM routing assumption) |

---

## 8. Coverage gap list (Phase 5)

| Gap | Severity | Notes |
|-----|-----------|--------|
| **`azure/` + `_litellm_auth_params`** | minor | No test asserts `api_key` passed for `azure/` prefix; behavior mirrors `openai/` — acceptable gap unless Azure becomes first-class in §2. |
| **Kill criteria — Flag 3** | — | Addressed: `completion_assistant_text` + `test_completion_assistant_text_*` and reactor integration tests. |
| **Public `react` symbols** | — | `tests/test_reactor.py` exercises `react`, `_parse_response` via `__new__`, and extraction helper. |

---

## 9. Verdict

**`fail`**

**Blocking items:** **F1** — bring `.dev/decision-logs/T7.md` and `.dev/decision-logs/T9.md` into compliance with plan §4 **T4** (remove, relocate, or clearly mark obsolete “Chosen approach” content so it cannot be read as current behavior; align T7 score-gate bullet with the 3-tuple contract).

**Non-blocking:** Address **F2**–**F3** and **S1** as part of the same editorial pass or follow-up.

---

## 10. Scout-prediction reconciliation

| Scout prediction (type) | Description (from context map) | Outcome | Finding ID |
|---------------------------|----------------------------------|---------|------------|
| Surface 1 (confirmed) | `ANTHROPIC_API_KEY` required at `load_config` → KeyError | **verified** — resolved via `getenv`; tests `test_load_config_without_llm_keys` | — |
| Surface 2 (confirmed) | `anthropic_api_key` on `HecklerConfig` | **verified** — field retained; reactor/tests/pipeline still use | O1 |
| Surface 3 (confirmed) | Default model `claude-haiku-...` vs LiteLLM ids | **verified** — default `openai/gpt-4o-mini` | — |
| Surface 4 (confirmed) | Prompt paths relative to package | **verified** — unchanged resolution in `Reactor.__init__` | — |
| Surface 5 (confirmed) | Monkeypatch `heckler.reactor.Anthropic` | **verified** — tests patch `litellm.completion` | — |
| Surface 6 (suspected) | `_extract_text_content` vs OpenAI choices | **verified** — `completion_assistant_text` + tests; old helper removed | — |
| Surface 7 (confirmed) | T7/T9 docs describe old contract | **verified** — errata added (`Landed:` blocks) but **F1**: main “Chosen approach” sections still read as current | **F1** |
| Flag 1 (ambiguity) | Credential ownership | **verified** — T10 + §2 + `load_config` | — |
| Flag 2 (vocabulary) | “4o mini” → `openai/gpt-4o-mini` | **verified** — config, README, `.env.example` | — |
| Flag 3 (missing_test_coverage) | Extraction / errors | **verified** — T3 tests for extraction + empty/none responses | — |

---

## Test command result

`python -m pytest tests/ -q` — **91 passed** (2026-05-09, workspace HEAD above).
