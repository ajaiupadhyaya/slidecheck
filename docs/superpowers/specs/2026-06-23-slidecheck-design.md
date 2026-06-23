# SlideCheck — PowerPoint Accessibility Auto-Fixer — Design

**Date:** 2026-06-23
**Status:** Approved design, pre-implementation

## Purpose

A college professor reviews many `.pptx` presentations to ensure they meet accessibility
requirements (state higher-ed policy, ADA Title II, Section 508, all of which point to WCAG).
Doing this by hand — opening each deck, running PowerPoint's limited built-in checker, and
fixing issues one by one — is slow and repetitive. SlideCheck automates the scan, fixes what
is safe to fix automatically, and produces a clear report of everything found and changed.

## Users & Workflow

- **Primary user:** a non-technical professor on **Windows**.
- **Workflow:** She drops one or many `.pptx` files onto the app window. For each file the
  app writes a corrected copy and a report next to the original, and opens the report.
- **Originals are never modified.** Output for `deck.pptx` is:
  - `deck_accessible.pptx` — corrected copy
  - `deck_a11y_report.html` — human-readable report (opens automatically)
  - `deck_a11y_report.json` — machine-readable report (for batch summaries / future use)

## Standard

Checks target **WCAG 2.1 AA + Section 508**. Where a state/institution rubric differs, the
rule set is structured so individual checks can be toggled or added later without touching
the engine.

## Architecture

Clean headless engine + thin GUI shell. The engine is fully testable and reusable as a CLI;
the GUI is a minimal drag-drop wrapper.

```
slidecheck/
  pptx_a11y/              # the engine (headless, tested)
    models.py            # Finding, Severity, Change, FileResult dataclasses
    loader.py            # open/validate a .pptx, isolate corrupt files
    checks/              # one module per rule; each: (presentation) -> list[Finding]
      __init__.py        # registry of all checks
      alt_text.py
      slide_titles.py
      contrast.py
      font_size.py
      tables.py
      link_text.py
      reading_order.py
      media_captions.py
      metadata.py
    fixers/              # one module per safe fix; each: (presentation) -> list[Change]
      __init__.py        # registry of all fixers
      alt_text.py        # embeds AI descriptions
      slide_titles.py    # inserts AI-suggested titles (flagged machine-generated)
      metadata.py        # document title / language
    alt_text_ai.py       # Claude vision integration (image -> description)
    report/
      html.py            # Findings + Changes -> styled HTML
      json.py            # Findings + Changes -> JSON
    pipeline.py          # orchestrates: load -> check -> fix -> save -> report
  cli.py                 # `slidecheck <file-or-folder>` — batch + used by tests
  gui.py                 # drag-drop window -> calls pipeline
  settings.py            # local storage of Anthropic API key + options
  packaging/
    slidecheck.spec      # PyInstaller spec
    build-windows.md     # how the Windows .exe is produced
  tests/
    fixtures/            # golden .pptx files with planted issues
    ...
```

### Data flow (per file)

```
load + validate
  -> run all checks            (collect Findings)
  -> run all fixers            (apply safe changes, collect Changes)
  -> save corrected copy       (deck_accessible.pptx)
  -> render HTML + JSON report
  -> (GUI) open the HTML report
```

### Core data model

- `Severity`: `ERROR` (blocks compliance) | `WARNING` (likely issue) | `INFO`.
- `Finding`: `check_id`, `severity`, `slide_index`, `shape_ref` (optional), `message`,
  `suggestion` (optional), `auto_fixed` (bool).
- `Change`: `fixer_id`, `slide_index`, `shape_ref` (optional), `description`,
  `machine_generated` (bool — true for AI alt text / titles).
- `FileResult`: `source_path`, `output_path`, `findings`, `changes`, `error` (optional).

## Checks (v0.1)

### Auto-fixed (applied to the corrected copy, listed in the report for spot-checking)

| Check | Detection | Fix |
|---|---|---|
| Missing alt text | Image/chart/picture shape with empty `descr` | AI-generated description embedded via the `cNvPr` `descr` attribute; `Change.machine_generated = true` |
| Missing slide title | Slide has no title placeholder text | AI-suggested title inserted into the title placeholder, clearly flagged machine-generated |
| Missing doc metadata | No document title or language set | Set core-properties title + language |

### Detected & reported (not safely auto-fixable — design/authorial intent required)

| Check | What it reports |
|---|---|
| Color contrast | Text/background ratio below 4.5:1 (3:1 for large text). Reports the actual ratio and a suggested compliant color **where colors are determinable**; explicitly marks `indeterminate` when theme inheritance makes the resolved color unknowable. Never auto-changes colors. |
| Font size | Text below a configurable minimum (default 18pt body / 24pt large guidance) |
| Tables | Merged cells, or no header row |
| Link text | Non-descriptive link text ("click here", "here", raw URLs) |
| Reading order | Shape z-order anomalies that imply a confusing screen-reader order |
| Media captions | Embedded video/audio with no caption track |

Each reported finding includes slide number, a shape reference, and a concrete suggested fix.

## Alt-text AI integration

- Uses Claude vision (`claude-sonnet-4-6`) to describe images/charts.
- The API key is entered once in the app's Settings and stored locally (`settings.py`,
  in the user's app-data dir — **not** in the repo).
- **Graceful degradation:** if no key is configured or the API is unreachable, alt-text
  generation is skipped and each missing-alt-text image is reported as an `ERROR` finding
  (flag-only) instead of failing the run.
- Decorative images: if a shape is already marked decorative, it is not flagged or described.

## Reliability rules

- **Per-file isolation:** a corrupt or unreadable file produces a `FileResult` with an
  `error` and the batch continues; one bad deck never aborts the run.
- **Never overwrite originals:** always write a `_accessible` copy; if that name exists,
  disambiguate rather than clobber.
- **Deterministic core:** all non-AI checks/fixers are deterministic; only alt-text/title
  generation calls the model.

## Reporting

- **HTML report:** grouped by slide, color-coded by severity, with a summary header
  (counts by severity, count auto-fixed, count needing manual attention). Machine-generated
  fixes are visually marked "review this". Self-contained (inline CSS), opens in any browser.
- **JSON report:** same data, for batch roll-ups and future integrations.
- **Batch summary:** when a folder is processed, an `index.html` links each file's report
  with its headline counts.

## Delivery / Packaging

- Developed and tested on macOS; the engine and GUI are cross-platform Python.
- The **Windows `.exe`** is produced by a Windows build step (GitHub Actions Windows
  runner, or PyInstaller run on a Windows machine) — a Windows binary cannot be
  cross-compiled from macOS. End result: a single double-clickable app, no Python install
  required. `packaging/build-windows.md` documents the exact steps.
- GUI uses a native drag-drop window (`tkinter` + `tkinterdnd2`), which bundles cleanly
  with PyInstaller and needs no browser runtime for the window itself (reports open in the
  user's default browser).

## Testing strategy

- **Golden fixtures:** small `.pptx` files in `tests/fixtures/` with deliberately planted
  issues (missing alt text, no title, low contrast, merged-cell table, bad link text, etc.).
- **Check tests:** each check asserts it finds exactly the planted findings and nothing on a
  clean deck.
- **Fixer tests:** assert the fix lands in the output file's XML (e.g. `descr` populated,
  title placeholder filled) and the original is unchanged.
- **Contrast math:** pure unit tests against known WCAG ratio examples.
- **AI alt text:** Claude calls mocked; one optional live smoke test gated behind an env flag.
- **Pipeline:** end-to-end on a fixture → corrected file + report produced; corrupt-file path
  yields an error result without crashing.

## Tech stack

- Python 3.12, managed with **uv** (`uv run` / `uv add` / `uv sync`).
- `python-pptx` (read/write), `Pillow` (image handling for vision), `anthropic` (Claude),
  `tkinterdnd2` (drag-drop), `pytest`.
- Packaging: `pyinstaller`.

## Out of scope (v0.1 — YAGNI)

- Editing/repairing color contrast automatically (reported only).
- Detecting "image of text" or "color used as sole information carrier" (unreliable to
  automate; deferred).
- Word/PDF/Google Slides support.
- Cloud hosting / multi-user accounts.
- In-app per-fix approval UI (current design applies safe fixes automatically and marks them
  for review in the report).

## Naming & location

- Project: **SlideCheck**, at `~/Documents/slidecheck`.
- Output files sit alongside each source deck.
