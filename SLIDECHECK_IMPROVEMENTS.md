# SlideCheck — Comprehensive Improvement & Build-Out Plan
**For Claude Code** | Based on `OVERVIEW.md` audit | Target: production-grade, professor-ready

---

## How to Use This File

This document is organized into **tiers** (Critical → High → Medium → Low) and **domains** (Checks, UX, Architecture, AI, Security, Testing, Deployment). Each item includes the specific files to touch, the concrete change to make, and why it matters. Work top-to-bottom; items within each tier are ordered by impact.

---

## TIER 1 — Critical Gaps (Fix These First)

### 1.1 Resolve the Four "Structural PASS" SCs — No Check Backs Them

**The problem:** `standards.py` catalogs 1.3.4 (Orientation), 1.3.5 (Identify Input Purpose), 1.4.2 (Audio Control), and 3.1.2 (Language of Parts) — all report PASS without any detection logic. This is legally misleading for a Section 508 tool.

**Fix:**

- **1.3.4 Orientation:** In `checks/`, add `orientation.py`. In OOXML a forced orientation is encoded on transitions (`<p:transition>`) or in presentation `defaultTextStyle`. Parse `prs.slide_width` vs `prs.slide_height` and flag when a slide's aspect ratio is locked landscape-only (16:9) **and** the deck contains a note saying "best viewed in landscape." This is a notes-text scan for sensory lock-in language.
- **1.3.5 Identify Input Purpose:** Mark all slides as N/A via `static_applicable=False` — this SC applies to form inputs, not static slides. Update `standards.py` to add this to the `INTERACTIVE_ONLY` set alongside 2.4.11, 2.5.7, 2.5.8, 3.3.8, 4.1.2.
- **1.4.2 Audio Control:** Promote to the `NEEDS_REVIEW` set alongside `1.2.2`. The existing `media.py` check already finds embedded audio; extend it to emit a second finding tagged `1.4.2` whenever it finds audio that auto-plays (check `<p:snd>` with `spd` or embedded in animation timeline `<p:timing>`).
- **3.1.2 Language of Parts:** Add `checks/language_parts.py`. Iterate every text run; when a run's `<a:rPr lang="">` attribute is present and differs from the deck's `dc:language`, emit a Warning finding under 3.1.2. Add an applier `set_run_language(prs, target, value) -> bool` to `appliers.py`.

**Files:** `pptx_a11y/standards.py`, `pptx_a11y/checks/orientation.py` (new), `pptx_a11y/checks/language_parts.py` (new), `pptx_a11y/checks/__init__.py` (add to module tuple), `pptx_a11y/appliers.py`.

---

### 1.2 Fix Font-Size Inheritance — Inherited Sizes Are Silently Skipped

**The problem:** `checks/font_size.py` only reads explicit run-level `sz` attributes. Sizes inherited from a placeholder's `<p:sp><p:spPr>`, theme body/title font, or `defaultTextStyle` are invisible to the check. A slide full of 12pt body text will pass if none of those runs have an explicit `sz`.

**Fix:**

1. In `textutil.py`, add `resolve_run_font_size(run, shape, slide, prs) -> int | None`. Walk the inheritance chain: run `rPr.sz` → paragraph `pPr` default → placeholder `txBody` defaults → layout placeholder → master placeholder → presentation `defaultTextStyle` → `None`.
2. Replace the direct `run.font.size` read in `font_size.py` with `resolve_run_font_size(...)`.
3. Add a corresponding `resolve_run_font_size` unit test in `tests/checks/test_font_size.py` covering each rung of the chain.

**Files:** `pptx_a11y/textutil.py`, `pptx_a11y/checks/font_size.py`, `tests/checks/test_font_size.py`.

---

### 1.3 Extend Alt-Text AI to Charts and Linked Pictures

**The problem:** Charts (`p:graphicFrame` containing `c:chart`) and linked pictures are flagged but never auto-described. This is acknowledged as a known limitation, but it is fixable.

**Fix:**

1. **Charts:** In `alt_text_ai.py`, add `describe_chart(chart_element, prs, describer) -> str | None`. Render the chart as an image by exporting it with `python-pptx`'s `chart.chart_type` metadata + `Pillow` (draw a simple representative bar/line from the chart's cached data `c:externalData` or `c:ser` series). Pass the rendered image to Claude vision. Alternatively, pass the chart's title (`c:title`) and series names as a text prompt to Claude (no vision needed): "Describe this chart for a screen reader: Title='Q3 Revenue', series=['Product A: 42%', 'Product B: 58%']."
2. **Linked pictures:** Resolve the `r:link` relationship to fetch the external image file (if local) or emit a more specific "linked image — cannot auto-describe, please provide alt text manually" finding instead of the generic flag.
3. **EMF/WMF:** When the image blob is EMF/WMF, pass the shape's name and slide title to Claude as a text-only prompt: "Suggest concise alt text for a shape named '{name}' on a slide titled '{title}'."

**Files:** `pptx_a11y/alt_text_ai.py`, `pptx_a11y/checks/alt_text.py`, `tests/test_alt_text_ai.py`.

---

### 1.4 Unify the Two Remediation Systems (Legacy Fixers vs. Appliers)

**The problem:** There are two parallel systems — `fixers/` (CLI/GUI) and `appliers.py` (web) — that do overlapping jobs. The legacy fixers auto-apply without user approval; the appliers require explicit plan approval but only run in the web path. This means the CLI gives no user control and the GUI gives no preview.

**Fix:**

1. **Deprecate** the legacy `fixers/` modules. Do not delete them yet — mark each with a module-level `# DEPRECATED: use appliers.py` comment and route `pipeline.process_file` to call `analyze()` → auto-accept all safe suggestions → call `apply_plan()`.
2. **Add a `--interactive` flag to the CLI.** When set, print each finding + suggested value and prompt `[A]ccept / [S]kip / [E]dit:` before adding it to the plan. This brings CLI to parity with the web studio.
3. **Add a "preview" panel to the GUI.** Before writing the `*_accessible.pptx`, show a scrollable list of pending changes with Accept All / Review Each buttons using Tkinter's `ttk.Treeview`.

**Files:** `pptx_a11y/pipeline.py`, `pptx_a11y/fixers/` (deprecate), `pptx_a11y/cli.py`, `pptx_a11y/gui.py`.

---

## TIER 2 — High-Impact Improvements

### 2.1 Add Three Missing Checks With Real Detection Value

These SCs are in the catalog but have no check or are under-specified:

#### 2.1.1 — 1.4.1 Use of Color (Strengthen)

Current check only flags hyperlinks with removed underlines. Expand to:
- Detect bar/pie charts where data series are distinguished **only** by fill color (no labels, no patterns). In `c:ser`, if `c:dLbls` is absent and `c:spPr/a:solidFill` is the only differentiator, flag it.
- Detect text runs where bold or italic was removed from previously bold/italic runs so only color distinguishes meaning (heuristic: adjacent runs with same font size where one has `a:solidFill` and `b=0`, `i=0`).

**File:** `pptx_a11y/checks/use_of_color.py` (extend).

#### 2.1.2 — 1.4.3 Contrast (Fix Grouped-Shape Gap)

The known limitation: grouped shapes measure contrast against slide background, not the group's own fill. Fix:
- In `checks/contrast.py`, when a shape is inside a `GroupShapes`, walk up the group chain to find the nearest ancestor with a solid `spPr/a:solidFill` and use that as the effective background.
- In `color.py`, add `resolve_effective_background(shape, slide, layout, master) -> RGBColor | None` that traverses the group→slide→layout→master chain.

**File:** `pptx_a11y/checks/contrast.py`, `pptx_a11y/color.py`.

#### 2.1.3 — 2.4.6 Headings and Labels (Strengthen Title Quality)

Current `title_quality.py` only flags generic ("Slide 1") or duplicate titles. Add:
- Flag titles over 80 characters (verbose, poor for screen reader navigation).
- Flag titles that are all-caps (screen readers may announce letter-by-letter in some modes).
- Flag numeric-only titles ("1", "2.3").
- Suggest a cleaned version as `suggested_value` in the web worklist.

**File:** `pptx_a11y/checks/title_quality.py`.

---

### 2.2 Add a Reading-Order Auto-Fixer

**The problem:** `reading_order.py` is detection-only and one of the most common real-world accessibility problems. Re-ordering shapes in the selection pane is something users would love auto-fixed.

**Fix:**
- Add applier `reorder_shapes(prs, target, value) -> bool` where `value` is a list of shape IDs in the desired tab order.
- In `analyze.py`'s `generate_suggestions`, when a `reading_order` finding fires, compute the suggested order: title placeholder first, then shapes in top-left → bottom-right reading order (sort by `shape.top * 10000 + shape.left`).
- Expose in the web worklist as an "Accept reorder" action with a visual before/after using slide thumbnail overlays.

**File:** `pptx_a11y/appliers.py`, `pptx_a11y/analyze.py`, `pptx_a11y/checks/reading_order.py`.

---

### 2.3 Improve AI Alt-Text Quality

**Current:** Single prompt, 125 char limit, no context about slide content.

**Improvements:**

1. **Slide-context injection.** Before describing an image, pass the slide title and surrounding text to Claude as context: `"This image appears on a slide titled '{title}'. Nearby text: '{body_text[:300]}'. Describe the image for a screen reader in one sentence under 125 characters."` This produces dramatically more relevant alt text.
2. **Decorative detection heuristic.** Before calling Claude, check if the image is a logo/watermark by examining: (a) shape name contains "logo", "watermark", "background", "footer"; (b) shape covers >90% of the slide area; (c) shape is behind all other shapes (z-order = 0). If any condition matches, suggest `mark_decorative` instead of `set_alt_text` in the web worklist.
3. **Retry + exponential backoff.** `ClaudeDescriber.describe_image` has no retry. Add `tenacity`-based retry (3 attempts, 1s/2s/4s backoff) for transient API errors (429, 529).
4. **Batch describe.** For CLI/GUI, collect all images first, then call Claude in parallel using `asyncio.gather` with a semaphore (max 5 concurrent). Currently each image is synchronous and sequential.

**File:** `pptx_a11y/alt_text_ai.py`.

---

### 2.4 Web Studio UX — Professor-Facing Improvements

The primary user is a non-technical professor. Current UX is already solid; these close the last gaps:

#### 2.4.1 — Slide Thumbnail Preview in Worklist

Each finding card should show a cropped thumbnail of the relevant shape, not just text. The API already computes base64 thumbnails for image findings — extend this to all findings by rendering a Pillow crop of the slide region around the flagged shape (`shape.left, shape.top, shape.width, shape.height` ± 10px padding).

**File:** `pptx_a11y/web/analyze_service.py`, `pptx_a11y/imageutil.py`.

#### 2.4.2 — "Fix All Like This" Button

For findings of the same check type (e.g., 50 slides all missing titles), add a "Fix All" button that bulk-applies the suggested value (or a user-edited value) to every finding of that `check_id`. In `app.js`, add `handleFixAll(checkId)` that iterates the worklist, accepts all matching findings with the same value, and updates the live score.

**File:** `public/app.js`.

#### 2.4.3 — Before/After Score Preview

When the user has accepted some fixes but not exported yet, show a split view: "Current score: 62 (D) → After fixes: 91 (A)". The optimistic score is already computed; surface it more prominently as a persistent banner rather than just the animated gauge.

**File:** `public/app.js`, `public/styles.css`.

#### 2.4.4 — Drag-and-Drop on Web (Remove Password Gate Option)

The password gate is appropriate for public deployment but adds friction for home/local use. Add an environment variable `SLIDECHECK_REQUIRE_PASSWORD=false` that bypasses the gate entirely for local-only deployments (where the professor runs it on her own machine). Still enforce HMAC compare when the gate is enabled.

**File:** `api/index.py`, `public/app.js`.

#### 2.4.5 — Progress Indicator During Analysis

For large decks (100+ slides), analysis can take 30+ seconds due to AI calls. Add a Server-Sent Events (SSE) stream endpoint `GET /api/analyze/progress` that emits `{slide: N, total: M, status: "describing image..."}` events, and update `app.js` to show a live progress bar while analysis runs.

**File:** `api/index.py`, `public/app.js`.

---

### 2.5 HTML Report — Make It Self-Contained and Professor-Shareable

The current HTML report references no external resources, which is good. Improve it:

1. **Embed slide thumbnails** for each finding in the HTML report (base64 inline images). A professor can email the report to a colleague who can see exactly which slide and shape has an issue.
2. **Add a "Summary for Administration" section** at the top: total slides, score, grade, number of Section 508 failures, number of WCAG-only warnings, and a one-sentence plain-English verdict ("This deck has 3 critical Section 508 violations that must be fixed before distribution.").
3. **Add a "Remediation Checklist" section** at the bottom: a printable checklist of all open findings grouped by type, with checkboxes. Useful for a professor who wants to fix manually in PowerPoint.
4. **Add ARIA landmarks** to the report HTML so it's navigable by screen reader: `<main>`, `<nav>` (slide jump links), `<section aria-labelledby>` per slide.

**File:** `pptx_a11y/report/html_report.py`.

---

### 2.6 CLI — Multi-Format Output and Exit Codes

1. **Exit code 1 for findings.** Currently the CLI exits `2` on path error and `0` on success. Add exit code `1` when the processed deck has open Error findings (distinguishes "ran fine, needs work" from "ran fine, all good") — useful for CI pipelines that auto-check instructor slide uploads.
2. **`--format` flag.** Add `--format [html|json|both|none]` to skip report writing when only the fixed deck is needed.
3. **`--dry-run` flag.** Run checks and print findings without writing any output files. Useful for quick audits.
4. **`--no-ai` flag.** Skip Claude calls entirely for fast offline scans.
5. **Colored terminal output.** Use `colorama` (already installable) or ANSI codes to color Error/Warning/Info counts in the console summary — red/yellow/blue matching the web severity pills.

**File:** `pptx_a11y/cli.py`.

---

## TIER 3 — Medium-Priority Enhancements

### 3.1 Google Slides / LibreOffice ODP Support

Many instructors use Google Slides. Add an `odp_adapter.py` that converts `.odp` → `.pptx` via LibreOffice's headless `--convert-to` before passing to the engine. The web API should accept `.odp` uploads (update the extension validator in `api/index.py`). In the desktop GUI, update the drop filter to include `.odp`. The CLI already handles paths; add ODP detection in `cli.py`.

**File:** `pptx_a11y/odp_adapter.py` (new), `api/index.py`, `pptx_a11y/cli.py`, `pptx_a11y/gui.py`.

---

### 3.2 Scoring Calibration — Make the Grade Scale Meaningful

Current deduction: Error=8, Warning=3, Info=1, starting from 100. A deck with 13+ errors scores 0 (F), but a single-error deck scores 92 (A-). This doesn't reflect real severity distribution.

**Proposed change:**
- Normalize score by slide count: `per_slide_penalty = total_penalty / slide_count`, then `score = max(0, 100 - per_slide_penalty * scaling_factor)`.
- Or: use a weighted percentage model — `score = 100 * (passing_checks / total_applicable_checks)` where each check is weighted by SC level (Error SCs count more).
- Add a `SCORING_MODEL` enum to `standards.py` with `ABSOLUTE` (current) and `NORMALIZED` modes, defaultable via env var `SLIDECHECK_SCORING=normalized`.

**File:** `pptx_a11y/standards.py`.

---

### 3.3 Plugin Architecture for Checks — Remove the Hard-Coded Module Tuple

Currently `load_all()` imports a hard-coded tuple of module names. Adding a check requires both the `@register` decorator and editing this tuple — a footgun.

**Fix:** Scan `pptx_a11y/checks/` for all `.py` files at runtime (excluding `__init__.py` and `registry.py`) and import them dynamically:

```python
import importlib, pkgutil
from . import checks
for _, name, _ in pkgutil.iter_modules(checks.__path__):
    importlib.import_module(f".{name}", package="pptx_a11y.checks")
```

This makes adding a check a one-file operation. No changes to `__init__.py` needed.

**File:** `pptx_a11y/checks/__init__.py`, `pptx_a11y/checks/registry.py`.

---

### 3.4 Database / History for the Web Studio

The web studio is currently fully stateless — no history. For a professor who runs it repeatedly on the same deck over a semester, add optional local history:

- Add a `SLIDECHECK_HISTORY_DIR` env var (default: disabled/`None`). When set, after each export, append a JSON record to a per-user history file: `{timestamp, filename, score_before, score_after, fixes_applied}`.
- Add a `GET /api/history` endpoint returning the last 20 records.
- Add a "History" tab in the web UI showing a timeline of past scans with before/after scores.

**File:** `api/index.py`, `public/app.js`, `public/styles.css`.

---

### 3.5 Accessibility of the Accessibility Tool — WCAG 2.1 AA Audit of the Web UI

The OVERVIEW.md claims the web front end targets WCAG 2.1 AA, but several areas need audit:

1. **Color contrast of severity pills.** Confirm the red/yellow/blue pill colors meet 4.5:1 against white text. If not, adjust `--error-color`, `--warning-color`, `--info-color` in CSS custom properties.
2. **Keyboard navigation of worklist cards.** Each Accept/Skip/Edit button must be reachable by Tab in document order. The current card layout may not guarantee this.
3. **Screen reader announcement of score updates.** The animated gauge changes score — confirm `aria-live="polite"` is on the score element and that the value is announced numerically ("Score: 87, grade B"), not just visually.
4. **Focus management after modal.** When a dialog closes (e.g., after "Set API key"), focus must return to the trigger button.
5. **Run axe-core** as part of CI against a rendered test page (`pytest-playwright` or a one-shot `node -e "require('axe-core')..."` headless check).

**File:** `public/styles.css`, `public/app.js`, `.github/workflows/` (add axe step).

---

### 3.6 Windows `.exe` — Auto-Updater and Installer

The current `.exe` is a flat folder (`dist/SlideCheck/SlideCheck.exe`) with no installer or auto-update. For a non-technical professor:

1. **Add an Inno Setup script** (`packaging/slidecheck.iss`) to produce a proper `.exe` installer with desktop shortcut, Start Menu entry, and uninstaller.
2. **Add a version-check on startup:** `GET https://api.github.com/repos/<owner>/slidecheck/releases/latest` → compare tag to `__version__`; show a Tkinter messagebox if an update is available.
3. **Bundle the Anthropic API key prompt into the installer** as an optional field, written to `settings.json` at install time.

**File:** `packaging/slidecheck.iss` (new), `pptx_a11y/gui.py`.

---

## TIER 4 — Polish and Long-Term

### 4.1 Internationalization (i18n) of Reports and UI

If the professor's students submit decks in other languages, the reports should be readable in those languages too. Add a `SLIDECHECK_LOCALE` env var. Externalize all user-facing strings in `report/html_report.py` and `public/app.js` into JSON locale files (`locales/en.json`, `locales/es.json`).

---

### 4.2 PowerPoint Add-In (Office JS)

The ultimate professor workflow: fix the deck without leaving PowerPoint. Add an Office JS task-pane add-in (`office_addin/`) that calls the SlideCheck API from within PowerPoint for Windows/Mac. The add-in manifest (`manifest.xml`) can be sideloaded by IT or distributed through AppSource.

---

### 4.3 Canvas LMS / Blackboard Integration

Many universities use Canvas. Add a `canvas_integration/` module that polls a Canvas course for newly uploaded `.pptx` files (via Canvas REST API), runs SlideCheck, and posts a comment on the submission with the accessibility score and report link. This would let a professor get automatic feedback on every slide deck posted to their course.

---

### 4.4 Structured JSON Conformance Report (VPAT Machine-Readable)

VPAT (Voluntary Product Accessibility Template) is the standard format for Section 508 conformance claims. Add a `report/vpat_report.py` that produces a machine-readable JSON following the OpenACR schema (`https://github.com/GSA/openacr`). This turns a SlideCheck run into a citable conformance document.

---

## Testing Gaps to Fill

| Gap | What to Add |
|---|---|
| No end-to-end test for CLI `--dry-run` / `--no-ai` / exit codes | Add `tests/test_cli.py` cases for each flag |
| No test for the font-size inheritance chain | Add `tests/checks/test_font_size_inherited.py` |
| No test for contrast in grouped shapes | Add `tests/checks/test_contrast_group.py` |
| No test for the new `language_parts` check | Add `tests/checks/test_language_parts.py` |
| No test for `reorder_shapes` applier | Add `tests/fixers/test_reorder_shapes.py` |
| No test for batch AI alt-text parallelism | Add `tests/test_alt_text_ai.py` async test |
| No test for `before/after` honest re-check in export (integration) | Add `tests/web/test_export_recheck.py` |
| No accessibility (axe-core) test of the web UI | Add `.github/workflows/a11y-check.yml` |
| Coverage of `pipeline.py` is not mentioned | Add `tests/test_pipeline.py` end-to-end smoke |

---

## Dependency Updates

| Package | Action | Reason |
|---|---|---|
| Add `tenacity` | `pip install tenacity` | Retry logic for Claude API calls |
| Add `colorama` | `pip install colorama` | Colored terminal output for CLI |
| Add `pytest-playwright` | dev dep | Headless browser tests for web UI |
| Add `axe-playwright-python` | dev dep | Automated WCAG testing of web UI |
| Evaluate `pillow-heif` | Optional | Support HEIF images embedded in decks |
| Pin `anthropic>=0.25` | Update | Batch/async API improvements |

---

## Quick-Win Checklist (Can Be Done in One Session)

> **Status — 2026-06-26 (shipped & deployed):** all quick wins below are done except the two marked *deferred* (they carry production-risk and need more care). The whole "structural PASS" gap (Tier 1.1) was also closed. See **Session notes** at the bottom of this section.

- [x] Move 1.3.5 to `INTERACTIVE_ONLY` (N/A) in `standards.py`; 1.3.4/1.4.2/3.1.2 → `NEEDS_REVIEW` (stop misleading PASS). _(4.1.2 was already N/A.)_
- [x] Add `--dry-run` and `--no-ai` flags to `cli.py`
- [x] Add exit code `1` to `cli.py` when open Error findings exist _(+ exit `2` when a deck can't be opened)_
- [ ] Add `resolve_run_font_size` inheritance chain to `textutil.py` — **deferred** (high false-positive risk in production; needs careful lxml inheritance walk + fixtures before it can ship safely)
- [x] Add slide-context to Claude alt-text prompt _(web path already had it; the CLI/GUI fixer now does too)_
- [ ] Add decorative-detection heuristic (logo/watermark/z-order) — **deferred** (needs a new `Finding` field + frontend handling to be meaningful; auto-marking decorative is a judgment call that risks hiding real images)
- [x] Extend `title_quality` to flag >80-char, all-caps, and numeric-only titles
- [x] Add "Summary for administration" block to `html_report.py`
- [x] Add ARIA landmarks (`<main>`, `<nav>`, `<section>`) to HTML report output
- [x] Add `SLIDECHECK_REQUIRE_PASSWORD=false` bypass to `api/index.py` _(+ `/api/config`; secure-by-default)_

**Session notes / deviation:** 3.1.2 (Language of Parts) is intentionally **not** implemented as the auto-check this plan proposed — a run whose `lang` differs from the document is *correct* foreign-language markup, so flagging/overwriting it would corrupt valid content. True 3.1.2 detection needs language identification of *unmarked* text. It is therefore classified `NEEDS_REVIEW` (honest, never a silent PASS). All changes shipped TDD-first with an adversarial multi-agent review (3 confirmed issues fixed); 262 tests green.

---

## File-by-File Change Map (Claude Code Reference)

```
pptx_a11y/
├── standards.py          ← Add 1.3.5/4.1.2 to INTERACTIVE_ONLY; SCORING_MODEL enum
├── textutil.py           ← Add resolve_run_font_size() inheritance chain
├── color.py              ← Add resolve_effective_background() for group chains
├── alt_text_ai.py        ← Slide-context prompt; decorative heuristic; tenacity retry; asyncio batch
├── analyze.py            ← reorder_shapes suggestion generation; chart description routing
├── appliers.py           ← Add reorder_shapes, set_run_language appliers
├── pipeline.py           ← Route through analyze+apply_plan; deprecate legacy fixers
├── cli.py                ← --dry-run, --no-ai, --interactive, --format flags; exit code 1; colorama
├── gui.py                ← Preview panel (ttk.Treeview); version-check on startup
├── checks/
│   ├── __init__.py       ← Dynamic pkgutil import (remove hard-coded tuple)
│   ├── orientation.py    ← New: 1.3.4 check (notes text scan for orientation lock-in)
│   ├── language_parts.py ← New: 3.1.2 check (run-level lang attribute diff)
│   ├── font_size.py      ← Use resolve_run_font_size instead of direct run.font.size
│   ├── contrast.py       ← Group-chain background resolution
│   ├── use_of_color.py   ← Chart series color-only detection; run color-only detection
│   └── title_quality.py  ← >80 char, all-caps, numeric-only title flags
├── report/
│   └── html_report.py    ← Embedded thumbnails; admin summary; remediation checklist; ARIA landmarks
└── web/
    └── analyze_service.py ← Per-finding shape thumbnail crops; SSE progress stream

api/
└── index.py              ← SLIDECHECK_REQUIRE_PASSWORD bypass; SSE /analyze/progress; /api/history; ODP upload support

public/
├── app.js                ← "Fix All Like This"; before/after score banner; SSE progress bar; History tab
└── styles.css            ← Contrast audit of severity pills; focus management

packaging/
└── slidecheck.iss        ← New: Inno Setup installer script

tests/
├── test_pipeline.py      ← New: end-to-end smoke
├── test_cli.py           ← New: flag coverage, exit codes
├── checks/
│   ├── test_font_size_inherited.py  ← New
│   ├── test_contrast_group.py       ← New
│   └── test_language_parts.py       ← New
├── fixers/
│   └── test_reorder_shapes.py       ← New
└── web/
    └── test_export_recheck.py       ← New

.github/workflows/
└── a11y-check.yml        ← New: axe-core CI step

pptx_a11y/ (new files)
├── odp_adapter.py        ← ODP → PPTX via LibreOffice headless
└── checks/
    ├── orientation.py    ← 1.3.4 (new)
    └── language_parts.py ← 3.1.2 (new)
```

---

## Summary Priorities by Persona

**For the professor (primary user):** 2.4.1 (thumbnails in worklist), 2.4.2 (Fix All), 2.4.4 (no-password local mode), 2.4.5 (progress bar), 2.5 (better HTML reports), 3.6 (installer).

**For Section 508 compliance:** 1.1 (fix structural PASS SCs), 1.2 (font-size inheritance), 2.1.2 (contrast in groups), 4.4 (VPAT output).

**For Claude Code's codebase health:** 1.4 (unify fixers), 3.3 (dynamic plugin import), testing gaps, dependency updates.

**For power users / IT:** 3.1 (ODP support), 3.4 (history), 4.3 (Canvas LMS), 2.6 (CLI flags).
