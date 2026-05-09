# Audit — litellm-provider-switch

**Audit document version:** **1.2** (re-audit after amendment **T5**; replaces **v1.1**, verdict `fail`, same date).

---

## 1. Audit metadata

| Field | Value |
|--------|--------|
| **Task name** | litellm-provider-switch |
| **Plan document** | `.dev/plans/litellm-provider-switch/plan.md` **v1.2.1** |
| **Audit date** | 2026-05-09 |
| **Repository HEAD (this pass)** | `94388a98ffd49b68ccbce21f238cabaf429ee166` |
| **Context map path** | `.dev/plans/litellm-provider-switch/context-map.md` |
| **Readiness verdict (map)** | CONDITIONAL |
| **Prior verdict (audit v1.1)** | `fail` — **F1** blocking on **T7**/**T9** narrative; **F2**, **F3** minor |
| **Remediation** | Plan amendment **T5** (packet `.dev/plans/litellm-provider-switch/packets/T5.md`); CHANGELOG **litellm-provider-switch** §**T5** |
| **Auditor focus (Phase 4)** | **Integration seams** (plan §5.4). **Failure paths**. **Regression surface** (pipeline **`HecklerConfig`**; CLI **`--list-devices`** only). Same rationale as v1.1. |

**Integration seams waiver:** Not applied.

---

## 2. Full artifact review (v1.2 — omission-free checklist)

| Artifact | Reviewed | Result |
|-----------|----------|--------|
| `.dev/plans/litellm-provider-switch/plan.md` | yes | **v1.2.1**; §0 notes amendment **T5**; §2 **LiteLLM call** *Landed* line documents **`openai/`** + **`azure/`** → **`openai_api_key`** / **`api_key`**, **`ollama/`** → **`api_base`**, bare id → **`openai_api_key`** — matches `heckler/reactor.py:_litellm_auth_params`. §7 **T5** spec aligns with executed remediation. |
| `.dev/plans/litellm-provider-switch/context-map.md` | yes | Pre-migration baseline; SHA unavailable; **historical** — no change required for T5. |
| `.dev/plans/litellm-provider-switch/packets/T1.md` … **T4.md** | yes | Original executor snapshots; unchanged by T5 (expected). |
| `.dev/plans/litellm-provider-switch/packets/T5.md` | yes | Amendment packet closes **F1**–**F3**; kill criteria consistent with edits observed in repo. |
| `.dev/decision-logs/T7.md` | yes | **Current behavior** first; score gate **`(None, latency_ms, DiscardReason.SCORE_GATE)`**; LiteLLM path explicit; **Historical** fenced; **Landed** retained for citation stability — **F1**/**F2** cleared. |
| `.dev/decision-logs/T9.md` | yes | **Current behavior** matches **`pipeline.py`** (direct **`react`**, 3-tuple, **`--list-devices`** only); **Historical** fenced — **F1** cleared. |
| `.dev/decision-logs/T10.md` | yes | Period-accurate **T1** snapshot (e.g. defer **`anthropic`** removal to **T2**); acceptable archival **Chosen approach** for config task. |
| `.dev/decision-logs/T11.md` | yes | **Chosen approach** names **`openai/`** + **`azure/`** → **`openai_api_key`**; **Assumptions** include **`azure/`**; **Landed** references **`heckler/reactor.py:_litellm_auth_params`** — **F3** cleared. |
| `heckler/config.py` | yes | Defaults and **`load_config()`** match §2 (`HECKLER_LLM_MODEL` strip, **`getenv`** for keys). |
| `heckler/reactor.py` | yes | **`completion_assistant_text`**, **`_litellm_auth_params`** (**`openai`/`azure`**, **`anthropic`**, **`ollama`**, bare id), lazy **`litellm`** in **`react`**, error log **`LLM API call failed`** — unchanged since v1.1 review; consistent with **T11**. |
| `heckler/pipeline.py` | yes | **`main`**: argparse **only** **`--list-devices`**; reaction path uses **`reactor.react`** and discard tuple — matches **T9** current behavior. |
| `pyproject.toml` | yes | **`litellm`** present; **`anthropic`** absent. |
| `tests/test_models.py` | yes | Config defaults, env overrides, whitespace **`HECKLER_LLM_MODEL`**, no **`KeyError`** on missing LLM keys. |
| `tests/test_reactor.py` | yes | **`litellm.completion`** mock; **`completion_assistant_text`**; empty choices / **`None`** response → **`LLM_ERROR`**. |
| `tests/test_pipeline.py` | yes | **`HecklerConfig(anthropic_api_key=...)`** still valid (plan §5.4 coupling). |
| `.env.example` | yes | Env keys subset of §2 / **`load_config`**; comments align with LiteLLM defaults. |
| `README.md` | yes | Table row **`OPENAI_API_KEY`** documents **OpenAI- and Azure-routed** models (**`openai/...`**, **`azure/...`**) — **F3** operator docs cleared. |
| `CHANGELOG.MD` | yes | **litellm-provider-switch** documents **T5** amendment and **§2** *Landed* alignment. |
| **pytest** | `python -m pytest tests/ -q` | **91 passed** at HEAD above (2026-05-09). |

**Working tree note:** `git status` at audit time showed **`M`** `.dev/plans/litellm-provider-switch/plan.md` and **untracked** `.dev/retrospectives/methodology/2026-05-09-litellm-provider-switch.md` — not part of litellm implementation contracts; no caveat on code-path findings.

---

## 3. Provenance log (Phase 0.5)

| Check | Result |
|--------|--------|
| **Context map SHA** | **unavailable** at scout time (unchanged). |
| **Plan post-execution SHA (v1.1 record)** | `1788bf89fe81e97999ec4fb5ff87ac1f6c14a556` — superseded by later commits; **v1.2 audit uses current HEAD** `94388a98…`. |
| **SHA comparison (map vs repo)** | Map cannot participate in per-file staleness; **no `context-map-stale`** filed. |
| **Scout grep gap** | **S1** remains an **observation**-grade feedback signal for future scouts (pre-migration map lacked **`HECKLER_LLM_MODEL`** / **`litellm`** tokens). |

---

## 4. Context chain completeness

| Artifact | Status |
|-----------|--------|
| Context map, plan **v1.2.1**, packets **T1**–**T5**, decision logs **T7**, **T9**, **T10**, **T11**, CHANGELOG, code/tests/docs in §2 | **complete** for this re-audit |

---

## 5. Cold-read notes (v1.2)

Prior **C1**–**C6** from v1.1 remain accurate where they describe code. **C3** (**Azure** branch): no longer a documentation gap — **T11**, **README**, plan §2 *Landed* align with **`_litellm_auth_params`**.

---

## 6. Findings table (v1.2)

| ID | Severity | Type | Status |
|----|-----------|------|--------|
| **F1** | ~~major~~ | contract-violation | **resolved** — **T7**/**T9** rewritten per **T5**; top-level **Current behavior**; obsolete narrative fenced **Historical**. |
| **F2** | ~~minor~~ | decision-log-stale | **resolved** — score gate and 3-tuple documented in **T7** **Current behavior**. |
| **F3** | ~~minor~~ | drift | **resolved** — **T11** + **README** + plan §2 document **`azure/`** / **`OPENAI_API_KEY`**. |
| **S1** | minor | scout-incomplete | **open (process)** — feedback to pre-plan-exploration; not a code defect. |

**No critical or major findings** remain.

---

## 7. Detailed findings (v1.2)

No findings above **minor** severity require blocking detail. **S1** is informational: early context map greps did not include post-migration vocabulary; predictable for a pre-migration scout run.

---

## 8. Adversarial test log (unchanged substance)

Scenarios from audit **v1.1** §7 re-validated against current **`reactor.py`** / **`pipeline.py`** / tests: integration seams and failure paths **pass**; **`azure/`** auth path still **unknown** from dedicated unit test (acceptable **minor** gap unless Azure becomes §2-first-class).

---

## 9. Coverage gap list

| Gap | Severity | Notes |
|-----|-----------|--------|
| **`azure/`** prefix in **`_litellm_auth_params`** | minor | No isolated unit test; mirrors **`openai/`**; documented in **T11** / **README**. |

---

## 10. Verdict

**`pass`** — merge-ready with respect to auditor-review gates. Residual **S1** is scout process feedback only.

---

## 11. Scout-prediction reconciliation (updated)

| Scout prediction | Outcome | Notes |
|------------------|---------|--------|
| Surface 7 (T7/T9 stale narrative) | **verified remediated** | **T5** + fenced **Historical**; **F1** closed. |
| Other rows from v1.1 | unchanged **verified** | Config, tests, LiteLLM mocks, Flag 1–3 |

---

## 12. Revision history

| Version | Date | Verdict | Summary |
|---------|------|---------|---------|
| **1.1** | 2026-05-09 | `fail` | **F1** blocking (**T7**/**T9**); **F2**, **F3** minor; HEAD `1788bf89…`. |
| **1.2** | 2026-05-09 | `pass` | **T5** remediation verified across decision logs, **T11**, **README**, plan §2, CHANGELOG; pytest green at `94388a98…`. |

---

## Test command result

`python -m pytest tests/ -q` — **91 passed** (HEAD `94388a98ffd49b68ccbce21f238cabaf429ee166`, 2026-05-09).
