# persona-system — T3 — Reactor constructor + UNKNOWN fallback

## Chosen approach

- **`Reactor.__init__(config, system_prompt, examples)`** — no filesystem reads; caller supplies resolved **`system_prompt: str`** and **`examples: list[dict[str, Any]]`**; **`_format_examples_block(examples)`** unchanged in signature and behavior (still only called from **`__init__`**).
- **`_parse_response`** — on **`ValueError`** from **`CommentType(type_val)`**, log **`LLM JSON unrecognized CommentType %r, falling back to UNKNOWN: %r`** and set **`ct = CommentType.UNKNOWN`**, then return **`ReactorResult`** (score gate in **`react`** unchanged).

## Alternatives rejected

- **Keeping `return None` for bad `type` strings:** rejected — §2 error envelope requires a **`ReactorResult`** with **`CommentType.UNKNOWN`** so high-confidence garbage types can flow to pacing/TTS instead of collapsing to **`LLM_ERROR`**.
- **Widening `_format_examples_block` or changing its signature:** rejected — not required; kill criterion (3) confirms caller surface is only **`Reactor.__init__`**.

## Assumptions made

- Callers ( **`pipeline.main`** in T5) load persona bundles and pass **`Persona.system_prompt`** / **`Persona.examples`** so **`Reactor`** stays free of **`prompts/`** path logic.
- **`CommentType.UNKNOWN`** is an acceptable spoken/logged type when the model emits an unknown label; operators relying on strict type sets filter downstream if needed.

## Items deferred

*(Section superseded by **T7** audit remediation, 2026-05-16. Prior deferred items described **pre-T5** state; **T5**/**T6** have landed. See **Landed** below.)*

## Landed (pipeline + tests — post-T5)

- **`heckler/pipeline.py`** — persona branch loads **`load_persona(prompts_root / persona_name)`**, applies **`apply_persona_overrides`**, then constructs **`Reactor(config, persona.system_prompt, persona.examples)`** (three-arg constructor per §2).
- **`tests/test_pipeline.py`** — integration and shutdown tests exercise the three-arg surface (including **`MagicMock`** monkeypatches using **`lambda *args, **kwargs:`** so **`Reactor`** receives **`config`**, **`system_prompt`**, and **`examples`**).
- **`tests/test_reactor.py`** — **`test_examples_json_types_are_comment_type_members`** reads **`prompts/heckler/examples.json`** (**T6**).

## Files added

- None ( **`tests/test_reactor.py`** gains two falsifiers for the **`react`** path with unrecognized **`type`** strings).
