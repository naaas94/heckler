# Heckler GUI — Dark Theme (implementation spec)

**Status:** Spec only (not implemented)  
**Stack:** PyQt6 ≥ 6.5, Fusion style, no new dependencies  
**Entry point:** `heckler-gui` → `heckler.gui.app:main`  
**Intent:** Single implementation pass — treat this document as the contract for the last fix on this feature.

Related notes: [`gui_thougths.md`](gui_thougths.md) (dark theme + transparency; transparency is **out of scope** here).

---

## Table of contents

1. [Goals and non-goals](#1-goals-and-non-goals)
2. [Current state](#2-current-state)
3. [Architecture](#3-architecture)
4. [Color system and palette](#4-color-system-and-palette)
5. [QSS supplement](#5-qss-supplement)
6. [Windows title bar and frame](#6-windows-title-bar-and-frame)
7. [File-level changes](#7-file-level-changes)
8. [Definition of Done](#8-definition-of-done)
9. [Manual UX verification matrix](#9-manual-ux-verification-matrix)
10. [Testing strategy](#10-testing-strategy)
11. [Trade-offs and frozen decisions](#11-trade-offs-and-frozen-decisions)
12. [Risks register](#12-risks-register)
13. [Coverage gaps and things easy to miss](#13-coverage-gaps-and-things-easy-to-miss)
14. [Kill criteria](#14-kill-criteria)
15. [Scope boundary vs gui_thougths.md](#15-scope-boundary-vs-gui_thougthsmd)
16. [Rollback](#16-rollback)
17. [Adversarial review summary](#17-adversarial-review-summary)

---

## 1. Goals and non-goals

### Goals

- Consistent **fixed dark** appearance on **Windows 10/11** (primary development OS).
- Apply globally to all widgets in `HecklerMainWindow` without per-widget styling in layout code.
- Single application point **before** any window or dialog is shown.
- Preserve existing behavior, tests, and headless CI (`QT_QPA_PLATFORM=offscreen`).
- **Dark client area and dark native title bar/frame** on Windows (not “Photoshop dark mode” with a light title bar).

### Non-goals

- Transparency, acrylic, Mica, or frameless/custom title bars.
- Light theme, runtime theme switcher, or following OS light/dark (`darkmode=2`, `colorSchemeChanged`).
- New Python dependencies (`qdarkstyle`, `pywin32`, frameless-window libraries).
- Custom widgets, icons, or Fluent/WinUI visual parity.
- Visual regression / screenshot CI.
- Changes to pipeline, controller, or `HecklerConfig` for theme (v1).
- Logs tab, persona-without-start workflow, transcription language switch (separate work).

### Delivery model

**One merge / one PR** satisfying [§8 Definition of Done](#8-definition-of-done). Do not ship “palette-only MVP” with a planned follow-up for scrollbars, group boxes, or title bar — bundle minimal QSS and platform hooks in the same change if manual checks require them.

---

## 2. Current state

| Area | State |
|------|--------|
| Entry | `heckler.gui.app:main` → `QApplication` → `HecklerMainWindow` |
| Styling | None — platform default (on Windows: often light native style) |
| Widgets | `QMainWindow`, `QGroupBox`, `QRadioButton`, `QComboBox`, `QPlainTextEdit`, `QLineEdit`, `QPushButton`, `QLabel`, `QStatusBar`, `QMessageBox` |
| Tests | `tests/test_gui.py` — pytest-qt, offscreen; no color/style assertions |
| Config | `HecklerConfig` has no GUI theme fields |
| Dependencies | `PyQt6>=6.5` in `pyproject.toml`; `pytest-qt>=4.2` in dev extras |

### Widget inventory (`heckler/gui/main_window.py`)

| Widget | Role |
|--------|------|
| `QGroupBox` “Mode” | Persona / Transcribe radios |
| `QLabel` + `QComboBox` | Persona picker |
| `QPlainTextEdit` | Live transcript + reactions (read-only) |
| `QGroupBox` “Session (transcribe)” | Session name `QLineEdit` |
| `QPushButton` | Start/Stop, Open transcripts folder |
| `QStatusBar` | Model load progress, status, errors (8s timeout) |

### Dialogs (`heckler/gui/app.py`, `main_window.py`)

| Dialog | Trigger |
|--------|---------|
| `QMessageBox.critical` | Model load failure → `app.quit()` |
| `QMessageBox.warning` | Pipeline / persona errors via `_show_error` |

Theme must be applied on `QApplication` **before** `HecklerMainWindow` and any `QMessageBox` so dialogs inherit the dark palette.

### Enable / disable matrix (behavioral — theme must support all states)

Implemented in `_apply_models_ready` and related handlers:

| State | Mode | Persona combo | Session field | Export | Start button |
|-------|------|---------------|---------------|--------|--------------|
| Loading models | any | disabled | disabled | disabled | disabled |
| Ready, stopped | persona | **disabled** | disabled | disabled | Start |
| Ready, stopped | transcribe | disabled | enabled | enabled | Start |
| Running | persona | **enabled** | disabled | disabled | Stop |
| Running | transcribe | disabled | enabled (mode logic) | enabled | Stop |

**UX note:** Persona combo is only enabled while the pipeline is **running** in persona mode. That confuses operators regardless of theme; do not reopen the dark-theme workstream to fix workflow — document as product behavior.

---

## 3. Architecture

### Module layout

```
heckler/gui/theme.py     # tokens, dark_palette(), dark_stylesheet(), apply_dark_theme()
heckler/gui/app.py       # qputenv (if needed), apply_dark_theme(app) after QApplication
heckler/gui/main_window.py   # unchanged (preferred)
tests/conftest.py        # optional: apply theme on pytest-qt qapp
tests/test_theme.py      # optional: palette unit tests without display
tests/test_gui.py        # optional: theme assertion via conftest
```

### Public API (`heckler/gui/theme.py`)

```python
# Color tokens (module constants; export for tests as needed)

def dark_palette() -> QPalette: ...
def dark_stylesheet() -> str: ...   # "" or minimal QSS (§5)
def apply_dark_theme(app: QApplication) -> None: ...
```

### `apply_dark_theme` behavior (order matters)

1. Optionally `qputenv("QT_QPA_PLATFORM", "windows:darkmode=1")` **before** `QApplication` exists — only if auto dark frame fails on target machines (see [§6](#6-windows-title-bar-and-frame)). **Do not** use `darkmode=2` (forces system dark palette; conflicts with fixed dark).
2. `app.setStyle("Fusion")`
3. `app.setPalette(dark_palette())`
4. `qss = dark_stylesheet()`; if `qss`: `app.setStyleSheet(qss)`

### Call site (`heckler/gui/app.py`)

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # If needed: qputenv before QApplication — see §6
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    # ... HecklerMainWindow, ModelLoadThread, etc.
```

### Conventions

- **Only** `heckler.gui.app:main` is the supported themed entry point.
- Do **not** call `apply_dark_theme` from `HecklerMainWindow` (hidden magic, double-apply risk).
- Do **not** add per-widget `setStyleSheet` in `main_window.py` unless explicitly scoped (e.g. status bar font — see [§15](#15-scope-boundary-vs-gui_thougthsmd)).

### Rejected approaches

| Approach | Why rejected |
|----------|----------------|
| QSS-only dark theme | High maintenance; misses disabled/focus states |
| Third-party dark packages | Violates no-new-deps |
| Per-widget styling in `main_window.py` | Spreads theme into layout |
| Default Windows (Vista) style | Forces light control chrome on dark systems |
| Frameless / custom title bar | Scope, snap, a11y, optional `pywin32` |
| `HecklerConfig` / `.env` theme toggle | YAGNI for v1 |

---

## 4. Color system and palette

### Design tokens

| Token | Hex | Palette / use |
|-------|-----|----------------|
| `bg_window` | `#1e1e1e` | `Window`, `Button` |
| `bg_base` | `#252526` | `Base` (inputs, feed) |
| `bg_alt` | `#2d2d30` | `AlternateBase` |
| `text` | `#cccccc` | `WindowText`, `Text`, `ButtonText` |
| `text_disabled` | `#6e6e6e` | Disabled group text/buttons |
| `text_placeholder` | `#888888` | `PlaceholderText` |
| `accent` | `#0078d4` (or `#3a96dd`) | `Highlight` |
| `accent_text` | `#ffffff` | `HighlightedText` |
| `border_subtle` | `#3f3f46` | QSS only (group boxes, status bar) |
| `link` | `#4ea1ff` | `Link`, `LinkVisited` |

Tune `text_disabled` and `text_placeholder` during manual pass if contrast fails WCAG-style checks on `#1e1e1e` / `#252526`.

### Palette groups (all required)

| Group | Required | Why |
|-------|----------|-----|
| `Active` | Yes | Normal UI |
| `Disabled` | **Yes** | Model-load gating, export/combo/matrix |
| `Inactive` | **Yes** | Session row in persona mode |
| `PlaceholderText` | **Yes** | Feed + session placeholders |

**Trap:** Setting only `Active` leaves disabled widgets with light-theme grays on a dark window.

### Color roles to set (per group)

**Active (and mirror for Disabled / Inactive with adjusted colors):**

`Window`, `WindowText`, `Base`, `Text`, `AlternateBase`, `ToolTipBase`, `ToolTipText`, `Button`, `ButtonText`, `BrightText`, `Link`, `LinkVisited`, `Highlight`, `HighlightedText`, `PlaceholderText`.

**Should also set:** `Light`, `Mid`, `Dark`, `Shadow` — Fusion uses them for borders/3D on Windows.

### Widget → role mapping (verification checklist)

| Widget | Expected look | Primary roles |
|--------|-----------------|---------------|
| Main window / central | Dark chrome | `Window` |
| `QPlainTextEdit` feed | Elevated panel | `Base`, `Text`; selection via `Highlight` |
| `QLineEdit` session | Same family as feed | `Base`, `Text`, `PlaceholderText` |
| `QComboBox` | Dark field + dropdown | `Base`, `Highlight` |
| `QPushButton` | Dark buttons, clear disabled | `Button`, `ButtonText` |
| `QRadioButton` / `QLabel` | Readable on window | `WindowText` |
| `QGroupBox` | Border + title | Palette + QSS (§5) |
| `QStatusBar` | Dark bar, readable text | `Window` / QSS |
| `QMessageBox` | Dark chrome | App palette |

### Title bar lightness rule (Qt 6.4+)

Qt applies dark window decoration when the default application palette is “dark”:

```text
WindowText.lightness() > Window.lightness()
```

With `#cccccc` on `#1e1e1e`, this must pass **after** `setPalette` and **before** `show()`. Requires **Fusion** — default Windows style ignores dark palette for native controls.

---

## 5. QSS supplement

Palette-first; add **minimal** global QSS in the **same PR** if manual pass fails.

### Order

`setStyle("Fusion")` → `setPalette(...)` → `setStyleSheet(...)`

Large global QSS can override palette roles and break disabled/focus states — keep QSS surgical (target ~40 lines or less).

### Candidates

```css
/* Illustrative — tune during implementation */

QGroupBox {
  border: 1px solid #3f3f46;
  margin-top: 6px;
  padding-top: 8px;
}
QGroupBox::title {
  subcontrol-origin: margin;
  color: #cccccc;
}
QStatusBar {
  border-top: 1px solid #3f3f46;
}
/* Add if manual pass fails: */
QScrollBar:vertical { /* thumb/track for dark feed */ }
QPlainTextEdit { /* only if white inset frame appears */ }
```

### When to include QSS

| Selector | Include if… |
|----------|-------------|
| `QGroupBox` / `::title` | Borders invisible or title clashes |
| `QScrollBar` | Thumb/track looks light on dark feed |
| `QStatusBar` | Bar blends into content |
| `QPlainTextEdit` | White inset border |

**Do not** QSS entire widget trees unless a specific bug is confirmed.

---

## 6. Windows title bar and frame

Highest UX risk for “unfinished” dark theme.

### Expected behavior (PyQt6 ≥ 6.5)

- `Fusion` + hand-crafted dark palette → dark **client area**.
- Qt 6.4+: dark **title bar/frame** when palette reads as dark (see [§4 lightness rule](#title-bar-lightness-rule-qt-64)).

### Failure modes

| Symptom | Likely cause | Mitigation |
|---------|--------------|------------|
| Light title bar, dark body | `Window` / `WindowText` not set; or wrong style | Fusion + full palette |
| Broken light controls on dark bg | Default Windows style | **Must** use Fusion |
| Win10 without auto dark frame | Platform default | `qputenv("QT_QPA_PLATFORM", "windows:darkmode=1")` before `QApplication` |
| App follows system light palette | Used `darkmode=2` | **Do not use** for fixed dark Heckler |

### Platform hook (no extra dependency)

From Qt docs — set in `main()` before `QApplication`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "windows:darkmode=1")
# Or: qputenv(b"QT_QPA_PLATFORM", b"windows:darkmode=1")
```

- `darkmode=1`: window decoration theming for custom dark palette.
- `darkmode=2`: also reads system dark palette — **conflicts with fixed dark product decision**.

Enable `darkmode=1` only if Fusion + palette alone leaves a light title bar on the developer’s Windows machine.

### Out of scope

Custom/frameless title bar, `pywin32` DWM hacks, third-party frameless libraries.

---

## 7. File-level changes

| File | Action | Notes |
|------|--------|-------|
| `heckler/gui/theme.py` | **Create** | Tokens, palette groups, `apply_dark_theme`, optional QSS |
| `heckler/gui/app.py` | **Modify** | Optional `qputenv`; `apply_dark_theme(app)` after `QApplication` |
| `heckler/gui/main_window.py` | **No change** (default) | Unless status-bar font scope accepted (§15) |
| `tests/conftest.py` | **Modify** (recommended if theme tests) | Apply theme on pytest-qt `qapp` |
| `tests/test_theme.py` | **Create** (optional) | Palette tests without widget tree |
| `tests/test_gui.py` | **Modify** (optional) | Lightness / Fusion asserts |
| `.dev/decision-logs/gui-dark-theme.md` | **Create** (recommended) | Frozen decisions for audit trail |
| `README.md` | **Modify** | 1–2 sentences under GUI section |
| `CHANGELOG.MD` | **Modify** | One bullet under unreleased |
| `pyproject.toml` | **No change** | |
| `heckler/config.py` | **No change** | v1 |

**Estimated size:** ~80–150 lines in `theme.py`, ~2–10 lines in `app.py`, small test additions.

---

## 8. Definition of Done

### 8.1 Automated (blocking)

- [ ] `pytest tests/test_gui.py -q` — all existing tests pass
- [ ] New: `test_dark_palette_window_text_lighter_than_window` (or equivalent) on `dark_palette()` — no display required
- [ ] Optional: `test_apply_dark_theme_sets_fusion_style` with conftest + pytest-qt `qapp`
- [ ] If conftest applies theme: no behavioral regression in existing GUI tests

### 8.2 Manual — Windows 10 or 11 (blocking)

- [ ] Title bar + frame dark (§6)
- [ ] No large white panels: central widget, feed, combos, inputs, buttons, group boxes, status bar
- [ ] Placeholder text readable in feed and session field
- [ ] Text selection in feed readable (copy transcript/reactions)
- [ ] Scrollbars acceptable on long feed content
- [ ] All states in [§9 UX matrix](#9-manual-ux-verification-matrix): disabled controls readable, not invisible
- [ ] `QMessageBox.critical` (model load fail) and `.warning` (pipeline error) readable
- [ ] Keyboard focus visible: Tab through radios, combo, fields, buttons
- [ ] Combo dropdown list dark when open (persona mode, running)

### 8.3 Manual — optional smoke

- [ ] Linux/macOS if supported — Fusion + palette generally work; title bar rules differ

### 8.4 Explicitly not required

- Fluent / WinUI look
- Persona swap without starting pipeline
- Logs tab
- Transparency
- Screenshot CI
- Following OS theme changes at runtime

---

## 9. Manual UX verification matrix

Walk every cell on a real Windows display after implementation.

| # | Models ready | Running | Mode | Check |
|---|--------------|---------|------|-------|
| 1 | No | No | any | Loading UI: disabled controls, status shows load progress |
| 2 | Yes | No | persona | Combo disabled, session disabled, export disabled, Start enabled |
| 3 | Yes | No | transcribe | Session enabled, export enabled, combo disabled |
| 4 | Yes | Yes | persona | Combo **enabled**, Stop, live feed append |
| 5 | Yes | Yes | transcribe | Export enabled, Stop, session field state correct |
| 6 | Yes | Yes | either | Mode switch while running (if applicable) — no illegible states |
| 7 | any | any | any | Trigger `_show_error` / warning dialog — readable |
| 8 | any | any | any | Simulate or force load failure — critical dialog readable |

### Status bar

Primary feedback during ~13s model load and runtime errors. Small default font on a dark bar is hard to scan — see [§15](#15-scope-boundary-vs-gui_thougthsmd) for optional font bump.

### Start / Stop button

Only label changes (`Start` / `Stop`); no distinct “destructive” styling in v1. Do not block dark-theme DoD on Stop coloring.

---

## 10. Testing strategy

### Headless CI

`tests/test_gui.py` sets `QT_QPA_PLATFORM=offscreen` via `setdefault`. Theme palette logic is display-independent; pixel appearance is not.

### Recommended tests

```python
# test_theme.py (example intent)
def test_dark_palette_reads_as_dark_for_window_frame():
    pal = dark_palette()
    assert pal.color(QPalette.ColorRole.WindowText).lightness() > \
           pal.color(QPalette.ColorRole.Window).lightness()

def test_disabled_group_differs_from_active():
    pal = dark_palette()
    # assert Disabled WindowText / Text differ from Active meaningfully
```

### Prod vs test drift

Tests construct `HecklerMainWindow` without `main()`. Options:

| Option | Pros | Cons |
|--------|------|------|
| **A** `conftest.py` autouse on `qapp` | Tests match production theme | Slight coupling |
| **B** Test `dark_palette()` only | Simple | Window tests unthemed |
| **C** Theme inside `HecklerMainWindow` | Always themed | Hidden magic — **rejected** |

**Recommendation:** **A** if adding theme assertions; **B** if tests remain behavior-only.

### Out of scope

- Screenshot / golden-file tests
- Full `main()` + `app.exec()` integration with real model load

---

## 11. Trade-offs and frozen decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Theme mode | **Fixed dark** | Matches `gui_thougths.md`; predictable for operators |
| Style | **Fusion** | Works with dark palette on Windows 11; Qt-recommended |
| Implementation | **Palette-primary + minimal QSS** | One-shot polish; palette alone often insufficient |
| System theme | **Ignore** (no `darkmode=2`, no `colorSchemeChanged`) | Conflicts with fixed dark |
| Config toggle | **No** v1 | YAGNI |
| `main_window.py` | **Avoid** | Theme centralized in `theme.py` / `app.py` |
| New dependencies | **No** | Constraint |
| Delivery | **Single PR** | Avoid 2nd/3rd “polish” passes |
| Windows `darkmode=1` | **Conditional** | Only if auto dark frame fails |
| Status bar larger font | **Product call** | High UX value; small diff — decide in same PR or explicit deferral (§15) |
| Start/Stop color | **Defer** | Not core to dark theme |

---

## 12. Risks register

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R1 | Light title bar with dark body | **High** | Palette lightness + Fusion; fallback `darkmode=1` |
| R2 | Incomplete Disabled/Inactive palette | **High** | Set all three groups in `dark_palette()` |
| R3 | Placeholder text illegible | Medium | `PlaceholderText` token ~ `#888888` |
| R4 | Light scrollbars on dark feed | Medium | Minimal `QScrollBar` QSS in same PR |
| R5 | Global QSS breaks focus/disabled | Medium | Surgical QSS; correct apply order |
| R6 | Tests pass, desktop looks wrong | Medium | Manual §8.2 is authoritative |
| R7 | High Contrast Windows | Low | Accept for dev tool |
| R8 | Operators blame theme for persona gating | Medium | Document workflow; not theme bug |
| R9 | Future widgets without theme | Low | Convention: no local stylesheets |
| R10 | PyQt6 minor version differences | Low | Verify on project venv; no new pin required |
| R11 | `QMessageBox` before theme applied | Low | Theme only in `app.py` before window |
| R12 | Offscreen vs desktop rendering | Low | Manual Windows pass required |

---

## 13. Coverage gaps and things easy to miss

### Surfaces originally under-specified

1. Native window chrome (§6) — **blocking**
2. `PlaceholderText` palette role — **blocking**
3. Text selection colors in read-only feed — **blocking**
4. Scrollbar styling — include QSS if needed
5. `Inactive` palette group — **blocking**
6. Combo dropdown popup — verify on Windows
7. `QMessageBox` critical vs warning — verify once each
8. Form layout: `QLabel` for session stays enabled when field disabled — OK if readable
9. Test harness: conftest theme hook if asserting palette on widgets
10. `qputenv` / `QT_QPA_PLATFORM` timing — **before** `QApplication`
11. Do not hook `QStyleHints.colorSchemeChanged` for fixed dark
12. Do not use default Windows Vista style
13. Decision log + README + CHANGELOG for operability

### Entry points

| Entry | Themed? |
|-------|---------|
| `heckler-gui` / `app.main()` | Yes (required) |
| Direct `HecklerMainWindow` in tests | Only if conftest applies theme |
| Future code importing window | Must use `app.main()` or call `apply_dark_theme` |

### Future GUI (do not block)

- Logs tab (`gui_thougths.md`) — global theme should apply to new widgets if no local overrides
- Transparency — separate spec
- Bigger status message — see §15

---

## 14. Kill criteria

**HALT merge** if:

1. On developer Windows machine, title bar stays **light** after Fusion + palette + optional `darkmode=1`.
2. Disabled persona combo (or other gated controls) is **unreadable**.
3. Any existing `tests/test_gui.py` test fails.

---

## 15. Scope boundary vs gui_thougths.md

| Item in `gui_thougths.md` | In dark-theme PR? |
|---------------------------|-------------------|
| Dark theme (`dak theme`) | **Yes** |
| More transparency | **No** |
| Bigger status (lower left) | **Decide now** — recommend including `statusBar().setFont(...)` (+1–2pt) in `theme.py` or `main_window.py` to avoid a 4th GUI pass; if excluded, document as separate ticket |
| Logs tab | **No** |
| Persona swap without start | **No** — controller/product |
| Lang switch (eng/spa) | **No** |

---

## 16. Rollback

1. Remove `apply_dark_theme(app)` from `app.py`.
2. Delete `heckler/gui/theme.py`.
3. Revert test/conftest/README/CHANGELOG/decision-log edits.

No impact on pipeline, config, or data.

---

## 17. Adversarial review summary

### Verdict

The approach (**Fusion + full palette + minimal QSS + Windows frame rule**) is sound and needs **no new dependencies**. The original high-level spec was **under-specified** for a true “last fix” on Windows.

### Must include in the single PR

1. Title bar / frame in DoD (§6, §8.2)
2. `Active` + `Disabled` + `Inactive` + `PlaceholderText` palettes (§4)
3. Selection / highlight colors for the feed (§4)
4. Minimal QSS for group box / scrollbar / status bar **if** manual pass fails (§5)
5. Automated palette lightness test (§10)
6. Full UX matrix manual pass (§9)

### Do not reopen this feature for

- Persona combo only enabled while running (workflow)
- Fluent-native appearance
- OS theme following
- Transparency

### Optional but high-value in same PR

- Status bar font size (+1–2pt)
- `.dev/decision-logs/gui-dark-theme.md`
- `conftest.py` theme autouse for test/production parity

---

## Implementation checklist (copy for PR description)

```markdown
- [ ] Add `heckler/gui/theme.py` (tokens, full palette groups, optional QSS)
- [ ] Wire `apply_dark_theme` in `heckler/gui/app.py` (optional `windows:darkmode=1`)
- [ ] Palette lightness test(s)
- [ ] Optional: conftest theme on qapp
- [ ] Manual Windows pass: §8.2 + §9 matrix
- [ ] README + CHANGELOG + decision log
- [ ] `pytest tests/test_gui.py -q` green
```

---

*Document generated from planning discussion (spec + adversarial pass). Update **Status** at top when implemented.*
