# SlideCheck

SlideCheck is a PowerPoint (`.pptx`) accessibility scanner and auto-fixer that audits decks against **WCAG 2.1 AA** and **Section 508**, automatically remediates the safe-to-fix issues (image alt text, slide titles, document metadata), and produces shareable HTML/JSON reports — all while **never modifying your original file** (fixes are always written to a separate `*_accessible.pptx` copy). One deterministic engine (`pptx_a11y`) is exposed three ways: a stateless **web "interactive remediation studio,"** a drag-and-drop **desktop GUI**, and a one-shot **command-line tool**. It was built for a college professor who has to vet presentations for accessibility compliance.

---

## The problem it solves & who it's for

University instructors, instructional designers, and anyone who publishes slide decks are increasingly required to ensure their materials meet accessibility law (Section 508) and best-practice standards (WCAG 2.1 AA). Checking a deck by hand — verifying every image has alt text, every slide has a title, the contrast is sufficient, links are descriptive, tables have header rows — is tedious and error-prone.

SlideCheck automates the audit, fixes what can be safely fixed without human judgment, and clearly flags what still needs a person's attention. The primary user is a non-technical professor who wants to drop a `.pptx` onto a window (or a web page) and get back a corrected deck plus a plain-English report — but the same engine serves power users via a scriptable CLI.

A core design promise runs through every entry point: **the original file is never altered.** Remediation always lands in a new file, so there is no risk of corrupting source material.

---

## Standards covered

SlideCheck's standards model lives in `pptx_a11y/standards.py`, which catalogs **25 WCAG success criteria (SC)** across the four POUR principles and distinguishes the Section 508 legal floor from WCAG 2.1/2.2 best practice.

### The 508 vs. WCAG distinction

- **Section 508 floor = WCAG 2.0 Level A/AA.** A criterion is tagged `section508=True` exactly when its WCAG version is `2.0` (18 of the 25 SCs).
- **WCAG 2.1 (3 SCs: 1.3.4, 1.3.5, 1.4.11) and WCAG 2.2 (4 SCs: 2.4.11, 2.5.7, 2.5.8, 3.3.8)** are flagged `section508=False` — best practice beyond the legal floor. (Note: 3.3.8 is Level A but was added in 2.2, so it is still not part of the 508 floor.)
- **SC 4.1.1 (Parsing) is intentionally excluded** — it was obsoleted/removed in WCAG 2.2.

### The catalog (25 SCs)

| Principle | Success Criteria |
|---|---|
| **Perceivable** | 1.1.1 Non-text Content, 1.2.2 Captions (Prerecorded), 1.3.1 Info and Relationships, 1.3.2 Meaningful Sequence, 1.3.3 Sensory Characteristics, 1.3.4 Orientation, 1.3.5 Identify Input Purpose, 1.4.1 Use of Color, 1.4.2 Audio Control, 1.4.3 Contrast (Minimum), 1.4.4 Resize Text, 1.4.5 Images of Text, 1.4.11 Non-text Contrast |
| **Operable** | 2.2.2 Pause Stop Hide, 2.3.1 Three Flashes, 2.4.2 Page Titled, 2.4.4 Link Purpose (In Context), 2.4.6 Headings and Labels, 2.4.11 Focus Not Obscured, 2.5.7 Dragging Movements, 2.5.8 Target Size |
| **Understandable** | 3.1.1 Language of Page, 3.1.2 Language of Parts, 3.3.8 Accessible Authentication |
| **Robust** | 4.1.2 Name, Role, Value |

**Interactive-only SCs** (1.3.5, 2.4.11, 2.5.7, 2.5.8, 3.3.8, 4.1.2) are marked `static_applicable=False` and always render as **N/A** for static slide decks, since they apply to interactive UI components / form inputs rather than presentations.

**Needs-review SCs** (`{1.4.1, 1.2.2, 1.3.2, 1.4.5, 1.4.11, 2.3.1, 1.3.4, 1.4.2, 3.1.2}`) can be *flagged* for human judgment but are never auto-passed — so the tool never reports a misleading silent PASS for a criterion it cannot actually verify.

---

## Three ways to use it

All three front ends drive the same `pptx_a11y` engine.

### 1. Web studio — "interactive remediation studio"

A zero-build, dependency-free single-page web client backed by a FastAPI app. After a password gate, you upload one or more decks, then work through a per-file "dossier": an animated score gauge, a coverage matrix, and a worklist of issue cards you **accept, edit, skip, or mark-decorative** one at a time. When you're done you export a fixed deck (or an HTML report). Nothing is stored server-side; your original file stays in the browser and is only transiently transmitted for processing.

```bash
# Local development
SLIDECHECK_PASSWORD=dev uv run uvicorn api.index:app --reload
# then open http://localhost:8000
```

### 2. Desktop GUI

A Tkinter drag-and-drop window (packaged as a Windows `.exe`). Drop one or more `.pptx` files onto it; SlideCheck runs the full pipeline, then opens the resulting report(s) in your browser. A "Set API key…" button lets you store an Anthropic key for AI alt text.

```bash
uv run slidecheck-gui     # console script -> pptx_a11y.gui:main
```

### 3. Command line (one-shot)

The fastest path for a single file or a whole folder. It loads each deck, runs all checks, auto-fixes the safe issues, and writes a `*_accessible.pptx` plus HTML and JSON reports next to the source. For folders it also writes a single `index.html` summary linking every per-deck report.

```bash
uv run slidecheck path/to/file-or-folder   # console script -> pptx_a11y.cli:main
```

**Flags:** `--dry-run` (audit only — print findings, write nothing), `--no-ai` (skip Claude entirely for a fast offline scan). **Exit codes** (CI-friendly): `0` all good · `1` ran fine but a deck has an open Error finding · `2` a path/deck could not be opened. In folder mode it skips Office lock files (`~$*`) and previously generated `*_accessible.pptx` outputs; a single deck failing prints to stderr without aborting the run, and the summary counts are colorized for an interactive terminal (suppressed under `NO_COLOR` or when piped).

---

## Features

### Accessibility checks

The detection layer is **12 self-registering check modules** that emit **13 check functions** (`slide_titles.py` registers two). Each produces `Finding` objects tagged with the SC number, severity, category, and a machine-readable remediation target. Group shapes are recursed into so nested content is checked.

| Check (`check_id`) | WCAG SC | Severity | What it flags | Auto-fixable? |
|---|---|---|---|---|
| `alt_text` | 1.1.1 | Error | Pictures/charts/linked images with empty alt text (skips decorative) | Yes (`set_alt_text`) — embedded raster only |
| `contrast` | 1.4.3 | Error / Info | Text/background contrast below 4.5:1 (3.0:1 for large text); theme-inherited colors → Info "indeterminate" | Yes for the Error case (`apply_contrast_color`) |
| `font_size` | 1.4.4 | Warning | Runs with explicit size < 18pt | Yes (`bump_font_size`) |
| `link_text` | 2.4.4 | Warning | Hyperlinks with empty / generic ("click here") / bare-URL text | Yes (`set_link_text`) |
| `media` | 1.2.2 | Warning | Any embedded audio/video (may lack captions) | No (detection only) |
| `metadata` (title) | 2.4.2 | Warning | Missing document title | Yes (`set_doc_title`) |
| `metadata` (language) | 3.1.1 | Warning | Missing document language | Yes (`set_doc_language`) |
| `motion` | 2.2.2 | Warning | Auto-advance timers / cannot-advance-by-click transitions | No (detection only) |
| `reading_order` | 1.3.2 | Info | Title placeholder is not the first shape | No (conservative, detection only) |
| `sensory` | 1.3.3 | Warning | Sensory-only instructions ("the red button", "the one on the left") | No (detection only) |
| `slide_title` | 2.4.2 | Error | Slide with an empty title placeholder | Yes (`set_title`) |
| `title_quality` | 2.4.6 | Warning | Generic ("Slide 1"), duplicate, overly-long (>80 chars), ALL-CAPS, or numeric-only titles | Yes (`set_title`) |
| `table` (header) | 1.3.1 | Error | Table missing a header row | Yes (`set_table_header`) |
| `table` (merged) | 1.3.1 | Warning | Table contains merged cells | No (detection only) |
| `use_of_color` | 1.4.1 | Warning | Hyperlink with underline explicitly removed (color-only cue) | No (detection only) |

Severities come from a three-value `Severity` enum (`error` / `warning` / `info`).

### Auto-fix capabilities

SlideCheck has **two parallel remediation systems** over the same deck model:

- **Legacy fixers** (`pptx_a11y/fixers/` — `alt_text`, `slide_titles`, `metadata`) run automatically in one monolithic pass via `pipeline.process_file`. This is the CLI/GUI path: it auto-applies a fixed set of fixes (alt text via AI, slide titles via AI with a "Slide N" fallback, document title + `en-US` language default).
- **Deterministic appliers** (`pptx_a11y/appliers.py`) execute a **user-curated fix plan** with **no AI or network calls**. This is the web export path. There are **9 appliers**, each `apply(prs, target, value) -> bool`, all of which catch every exception and never raise:

| Applier | Action |
|---|---|
| `set_alt_text` | Sets the picture/shape `cNvPr` alt-text description |
| `mark_decorative` | Adds `<adec:decorative val="1">` (2017 decorative namespace) |
| `set_title` | Sets a slide's title placeholder text |
| `set_doc_title` | Sets the document core-properties title |
| `set_doc_language` | Sets the document language |
| `set_link_text` | Sets a hyperlink run's text, preserving the hyperlink relationship |
| `set_table_header` | Turns on `table.first_row` |
| `apply_contrast_color` | Recolors text to a compliant value (`[r,g,b]` or `#rrggbb`) |
| `bump_font_size` | Sets run size, enforcing an **18pt floor** regardless of the supplied value |

Run-level appliers defensively reject shape-level targets (`hasattr(run, "hyperlink")`) so a misrouted target can't corrupt a text frame. `apply_plan` runs each `{action, target, value}` item in order and returns parallel `{action, ok}` results — one failing item never aborts the rest, and an unknown action returns `ok: false`. `mark_decorative` is not produced by any check; it's an alternative the web client offers for an alt-text finding.

### AI alt-text generation

Alt text and slide-title suggestions are powered by **Anthropic Claude vision** (`claude-sonnet-4-6`) behind a swappable `Describer` protocol:

- **`ClaudeDescriber`** encodes the image as base64 and asks for "one sentence, under 125 characters" alt text (`max_tokens=120`); `suggest_text` produces short titles (`max_tokens=40`).
- **`NullDescriber`** is used whenever no API key is present and returns `None` for everything.
- **Graceful degradation:** with no key or on *any* API error, the describer returns `None`, so the issue stays **flagged for manual fix** rather than silently auto-filled — the scan never crashes. Client construction failure is memoized (`_client_failed`) so it isn't retried per image.
- **`CappedDescriber`** (web only) bounds wall-clock time on serverless by describing only the first *N* images per request (title suggestions are always delegated since they're cheap).
- The API key resolves from a GUI-persisted `settings.json` (stored with owner-only `0600` permissions) or the `ANTHROPIC_API_KEY` environment variable.

### Scoring, letter grade & coverage matrix

`standards.py` provides pure, deterministic, reproducible scoring (no I/O, no `python-pptx`):

- **Score (0–100):** start at 100, deduct per *open* finding — **error 8, warning 3, info 1** — clamped at 0. Auto-fixed findings never penalize.
- **Letter grade:** A ≥ 95, B ≥ 85, C ≥ 70, D ≥ 55, else F.
- **Coverage matrix:** one row per cataloged SC, numerically sorted, classified by strict priority **N/A > FAIL > NEEDS_REVIEW > PASS**.

> **Honest classification:** SCs with no reliable automated detector are never reported as a silent PASS. **1.3.5 Identify Input Purpose** is N/A for static decks; **1.3.4 Orientation**, **1.4.2 Audio Control**, and **3.1.2 Language of Parts** are surfaced as *Needs review* rather than auto-passed. (3.1.2 is deliberately not auto-checked: a run carrying a differing `lang` attribute is *correct* foreign-language markup, and detecting an *unmarked* foreign passage would need language identification.)

### Reporting

- **HTML report** (`<stem>_a11y_report.html`): findings grouped by slide with severity pills and auto-fixed/review tags. Opens with a **"Summary for administration"** block — score/grade, open Section 508 issue count, open warnings, auto-fixed and needs-manual counts, plus a one-sentence plain-English verdict — and is itself navigable by screen reader via ARIA landmarks (`<main>`, a `<nav>` of slide jump-links, and one `<section aria-labelledby>` per slide).
- **JSON report** (`<stem>_a11y_report.json`): the full `FileResult` serialized (with `Severity` as its string value).
- **Batch index** (`index.html`): a folder-level summary table with columns *File, Errors, Warnings, Info, Auto-fixed, Needs manual fix, Report*. It embeds a marker comment (`<!-- slidecheck-batch-index -->`) so re-runs overwrite SlideCheck's own index but never clobber a user's pre-existing `index.html` (it falls back to a unique filename instead).
- **"Needs manual fix"** counts open (not auto-fixed) error + warning findings — the figure that tells a reviewer how much hands-on work remains.

---

## How it works

### The CLI/GUI pipeline (`pipeline.process_file`)

```
load -> check -> fix -> mark-fixed -> save -> report
```

1. **Load** the source via `python-pptx` (`LoadError` on any open failure).
2. **Check:** `load_all()` imports all 12 check modules (triggering `@register`), then every registered check runs and emits `Finding`s.
3. **Fix:** the 3 legacy fixers mutate the in-memory deck, producing `Change`s.
4. **Mark-fixed:** `_mark_fixed` correlates each `Change` back to its originating `Finding` (via `_FIX_MAP`, keyed on `fixer_id`/`slide_index`/`shape_ref`) and sets `auto_fixed=True`, so reports and the score show resolved issues as resolved.
5. **Save** to a *new* file: `unique_path(out_dir/<stem>_accessible.pptx)` — appending `_1`, `_2`, … if needed so prior outputs are never overwritten. The source path is only ever read.
6. **Report:** write HTML + JSON.

### The web's stateless two-phase flow

The web layer never auto-applies fixes. Instead it splits analysis from remediation so the user approves each change:

1. **Analyze (`POST /api/analyze`):** `analyze_upload` writes the uploaded bytes into a `TemporaryDirectory`, runs the checks, generates per-finding `suggested_value`s (deterministic defaults like `18`/`en-US`, or AI text), computes the score and coverage matrix, and attaches base64 thumbnails for image findings. **Nothing is saved.**
2. **Accept / edit / skip:** the browser builds a fix plan client-side as the user works through the worklist. The live score gauge rises optimistically as fixes are accepted.
3. **Export (`POST /api/export`):** `export_with_plan` re-receives the original bytes plus the JSON plan, applies exactly the approved actions in a `TemporaryDirectory`, saves a `*_accessible.pptx`, then **re-opens and re-checks the saved file** for an *honest "after" report* reflecting the real output. The fixed deck is returned as base64 for the browser to download.

There is no server-side session: the server is a pure function of its inputs on each call, and the original file lives only in browser memory.

---

## Architecture

One engine, three front ends.

```
                      ┌─────────────────────────────────────────┐
   CLI (cli.py) ──────┤                                          │
   GUI (gui.py) ──────┤   pptx_a11y engine                       │
   Web (api/index.py)─┤   loader · checks/ · fixers/ ·           │
        + public/     │   appliers · analyze · standards ·       │
                      │   refs · textutil · color · pipeline ·   │
                      │   report/ · alt_text_ai · settings       │
                      └─────────────────────────────────────────┘
```

**Key engine modules:**

- `pipeline.py` — load→check→fix→save→report orchestrator; `unique_path`, `_mark_fixed`.
- `models.py` — `Severity` enum, `Finding`, `Change`, `FileResult` dataclasses.
- `loader.py` — `load_presentation` wrapping `python-pptx`.
- `checks/` — 12 registered detection modules + the registry/`load_all`/`iter_shapes`.
- `fixers/` — 3 legacy auto-fixers (`alt_text`, `slide_titles`, `metadata`).
- `appliers.py` — 9 deterministic appliers + `apply_plan` (web path).
- `standards.py` — SC catalog, score, coverage matrix.
- `analyze.py` — web/JSON analysis API: `run_checks`, `generate_suggestions`, `finding_to_dict` (synthesizes a unique id `check_id:slide:shape_ref:index` to prevent collisions), `analyze`.
- `refs.py` — shape/run addressing; `resolve_target` maps a finding's target dict back to a live object (group-aware).
- `textutil.py` / `color.py` — run/color extraction helpers and WCAG contrast math.
- `alt_text_ai.py` + `settings.py` — Claude integration and secure key handling.
- `report/` — `html_report`, `json_report`, `batch_index`, `summary_counts`.
- `web/` — `analyze_service`, `export_service`, `describers` (`CappedDescriber`).

**Plugin pattern:** checks and fixers self-register via an `@register` decorator into module-global lists; `load_all()` imports a hard-coded tuple of module names to trigger registration. Adding a check requires both the decorator *and* adding its name to that tuple.

**Front ends:**

- **`public/`** — `index.html` (static shell), `app.js` (~790 lines of vanilla JS: gate auth, analyze, dossier/gauge/coverage/worklist rendering, the accept/skip/undo state machine, plan assembly, export), `styles.css` (design tokens, gauge geometry, severity rail, responsive + reduced-motion blocks).
- **`api/index.py`** — FastAPI app with `/api/health`, `/api/auth`, `/api/analyze`, `/api/export`.
- **`cli.py` / `gui.py`** — thin desktop wrappers; the GUI cleanly separates pure, testable helpers (`handle_drop`, `_open_reports`, `drop_summary`, `_parse_drop`) from the un-covered Tkinter window wiring.

---

## Privacy & security model

- **Original never modified.** The CLI reads the source and saves only to a different `*_accessible.pptx`. The web paths write bytes into an ephemeral `TemporaryDirectory`, process there, and delete the whole directory on return — nothing persists between requests or phases.
- **Original stays client-side (web).** The source `.pptx` is held in browser memory, transmitted only transiently for processing, and the corrected file comes back as base64 for local download. No upload is retained.
- **Password gate.** Every mutating endpoint (`/api/auth`, `/api/analyze`, `/api/export`) is protected by a shared password compared with `hmac.compare_digest` (constant-time) against `SLIDECHECK_PASSWORD`. A missing server password returns **503** (checked before the **401** for a wrong password); `/api/health` and `/api/config` are exempt. The web client validates the password at the gate (`/api/auth`) before entry and surfaces distinct messages for 401 / 503 / network failures; a 401 mid-session clears the stored password and returns to the gate. For a purely local/offline deployment, `SLIDECHECK_REQUIRE_PASSWORD=false` disables the gate entirely (the front end reads `/api/config` and skips it) — the gate is **on by default** and only the literal `false` disables it, so the public Fly deployment is unaffected.
- **XSS-safe rendering.** Every server-derived string reaches the DOM via `textContent` (or an `esc()` helper when composed); `innerHTML` is used only for author-authored static icon markup. Thumbnail `src` values come from the service's own `data:` URIs.
- **Input hardening.** Uploads are validated for the `.pptx` extension (400) and a size limit (413, default 50 MB / 40 MB on Fly); an invalid or non-list fix plan returns 400; load-failure error messages scrub the internal temp path so no server internals leak. The number of AI image calls per request is capped to bound serverless time/cost.
- **Secure key storage.** The GUI persists the API key to `settings.json` with owner-only `0600` permissions (and `0700` parent dir), re-applying `chmod` to defend against pre-existing-file permission leaks.
- **Self-accessible UI.** The web front end itself targets WCAG 2.1 AA: skip link, ARIA live regions, `aria-labelledby`, `:focus-visible` rings, a `prefers-reduced-motion` block, status conveyed by text labels (never color alone), and `[hidden]` enforcement.

---

## Tech stack

- **Language/runtime:** Python ≥ 3.12, managed with **uv**.
- **Core:** `python-pptx` (deck model), `lxml` (OOXML element manipulation, e.g. the decorative element), `Pillow` (web thumbnails), `dataclasses` + `enum`.
- **AI:** Anthropic SDK — `claude-sonnet-4-6` vision.
- **Web:** FastAPI + Starlette, Uvicorn (ASGI), `python-multipart`; vanilla JS front end (Fetch, `FormData`, `sessionStorage`, inline SVG gauge, base64→Blob download) — **no framework, no build step**.
- **Desktop:** Tkinter + `tkinterdnd2` for native drag-and-drop.
- **Packaging/CI:** setuptools build backend, PyInstaller (Windows `.exe`), Docker (`python:3.12-slim`), Fly.io, GitHub Actions.
- **Testing:** pytest + httpx test client.

---

## Testing & quality

- Run the suite with `uv run pytest` — current state: **262 passed, 1 skipped** in ~2.3s.
- **33 test files**, organized across the root engine tests and `tests/checks/`, `tests/fixers/`, `tests/report/`, and `tests/web/` subdirectories. Heaviest coverage is on `appliers`, `analyze`, the web `api`/`export_service`, and the `slide_titles` checks.
- The Tkinter GUI is split so its pure logic is unit-tested (with stub describers and an injectable browser opener) while the window-wiring `main()` is explicitly excluded from coverage — letting the tests run headless in CI.

---

## Deployment

- **Web app — Fly.io.** App name `slidecheck-a11y` (region `iad`), served by a `python:3.12-slim` container running `uvicorn api.index:app` on port 8080. Machines suspend when idle (`auto_stop=suspend`, `min_machines_running=0`) and resume from a RAM snapshot in ~1s. By Fly convention the host is `slidecheck-a11y.fly.dev`. Deploy with:
  ```bash
  fly launch --no-deploy
  fly secrets set ANTHROPIC_API_KEY=... SLIDECHECK_PASSWORD=...
  fly deploy
  ```
  Configuration env vars: `SLIDECHECK_PASSWORD` (access gate), `SLIDECHECK_REQUIRE_PASSWORD` (set to `false` to disable the gate for local use; defaults on), `ANTHROPIC_API_KEY` (server-side Claude key), `SLIDECHECK_MAX_UPLOAD_MB` (default 40 on Fly), `SLIDECHECK_MAX_AI_IMAGES` (default 40). The web container's `requirements.txt` deliberately excludes `tkinterdnd2` and all dev/test tooling.
- **Windows desktop `.exe`.** Built with PyInstaller from `packaging/slidecheck.spec` (bundling `pptx_a11y/gui.py` + `tkinterdnd2` + `pptx`, windowed, `console=False`) to `dist/SlideCheck/SlideCheck.exe` — the whole folder must be kept together. Build locally on Windows (`uv run pyinstaller packaging/slidecheck.spec`) or via the **"Build Windows app"** GitHub Actions workflow (triggered on `v*` tags or manual dispatch; downloads the `SlideCheck-windows` artifact). It **cannot** be cross-compiled from macOS.
- **Version:** `0.3.0` (tags `v0.2.0`, `v0.3.0`).

---

## Known limitations

These are honest, known limitations baked into the checks' behavior (the first six are also called out in `README.md`):

1. **Charts and linked pictures** are flagged but not auto-described — only embedded raster images (PNG/JPEG/GIF/TIFF) receive AI alt text.
2. **EMF/WMF and other non-raster formats** always require a manual fix.
3. **Contrast** resolves the real background (shape → slide → layout → master) and only assumes white when none is a solid color — saying so in the message. Theme/inherited *text* colors are reported as "indeterminate" (Info), not guessed/failed.
4. **Font-size** checks only see explicit run-level sizes; sizes inherited from a placeholder are not measured.
5. **Uncaptioned media** — every embedded audio/video is flagged as "may lack captions" because the tool cannot inspect for an actual caption track.
6. **Text inside grouped shapes** has its contrast measured against the slide/layout/master background, not the group's own fill.
7. **Unverifiable SCs** — 1.3.4 (Orientation), 1.4.2 (Audio Control), and 3.1.2 (Language of Parts) have no reliable automated detector, so they are surfaced as *Needs review* rather than verified (1.3.5 is N/A). They are honestly classified, never silently passed.
8. The web deployment depends on the `ANTHROPIC_API_KEY` environment variable; without it, `NullDescriber` is used and no AI alt text is generated.

---

## Repository layout

```
slidecheck/
├── pptx_a11y/                 # the engine
│   ├── pipeline.py            # load→check→fix→save→report orchestrator
│   ├── models.py              # Severity, Finding, Change, FileResult
│   ├── loader.py              # load_presentation (python-pptx)
│   ├── analyze.py             # run_checks, generate_suggestions, analyze()
│   ├── appliers.py            # 9 deterministic appliers + apply_plan
│   ├── standards.py           # SC catalog, score(), coverage_matrix()
│   ├── refs.py / textutil.py / color.py / imageutil.py
│   ├── alt_text_ai.py         # Describer protocol + Claude/Null describers
│   ├── settings.py            # secure API-key storage, get_describer
│   ├── cli.py                 # `slidecheck` entry point
│   ├── gui.py                 # `slidecheck-gui` entry point
│   ├── checks/                # 12 detection modules (+ registry)
│   ├── fixers/                # 3 legacy auto-fixers
│   └── report/                # html_report, json_report, batch_index
├── api/index.py               # FastAPI ASGI app (analyze + export)
├── public/                    # web front end (index.html, app.js, styles.css)
├── web/ (pptx_a11y/web/)      # analyze_service, export_service, describers
├── tests/                     # 33 files / 239 tests (root + checks/fixers/report/web)
├── packaging/                 # slidecheck.spec + build-windows.md
├── Dockerfile / fly.toml      # Fly.io container deploy
├── .github/workflows/build-windows.yml
├── pyproject.toml / requirements.txt
└── README.md
```
