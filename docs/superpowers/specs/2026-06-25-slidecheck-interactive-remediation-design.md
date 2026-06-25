# SlideCheck → Interactive Remediation Studio — Design

**Date:** 2026-06-25
**Status:** Approved (owner granted full autonomy while away)
**Author:** ajaiupadhyaya (with Claude Code), grounded in a 4-stream research workflow + engine map

## Problem

SlideCheck today is a one-shot scanner: upload → static HTML report → download a deck with 3 auto-fixes (alt text, titles, metadata). The owner's verdict: *"still static and not very effective."* It must become a **one-stop shop for making a presentation fully accessible** — it should actively guide a non-technical professor through fixing **every** issue and hand back a genuinely compliant deck.

## Vision

An **interactive remediation studio**. Drop a `.pptx` → see one honest **accessibility score + letter grade** and a plain-language **WCAG/508 coverage matrix** → work a **guided, per-issue worklist** where each issue explains itself, shows the offending content (the real embedded image for alt-text issues; the exact text snippet otherwise), and offers an **AI-drafted fix the user can Accept / Edit / Skip** → the score climbs live → one click **exports a fully-fixed deck** (containing exactly the approved fixes) plus a compliance report.

## Load-bearing architecture decision: stateless two-phase

No server sessions. The original file stays in the browser.

1. **`POST /api/analyze`** — receives the upload, runs all checks, generates AI suggestions (alt text via vision, titles, link text), and returns **structured findings JSON + score + coverage matrix + per-issue context (image thumbnails / text snippets)**. It does **not** save anything and does **not** return the deck (the browser already holds it).
2. Browser builds a **fix-plan** from the user's Accept/Edit choices: a list of `{target, action, value}`.
3. **`POST /api/export`** — receives the **original file + the approved fix-plan**, applies exactly those fixes **deterministically (no AI)**, returns the fixed `.pptx` + a final HTML report.

Why: keeps the in-memory, nothing-persisted, password-gated, suspend-on-idle Fly deployment working with **no new infrastructure**; AI cost/latency live only in `analyze`; `export` is pure python-pptx (fast, free, repeatable); a suspend between the two requests can't lose work because the client holds the state.

`process_file` (the all-at-once CLI/GUI path) stays **unchanged** — the interactive flow is a thin new layer over the same checks/fixers registries (single-sourced engine).

## Data model

Extend `Finding` (backward-compatible defaults so the CLI/GUI/report keep working):

| New field | Type | Purpose |
|---|---|---|
| `sc_refs` | `list[str]` | WCAG success criteria, e.g. `["1.1.1"]` |
| `wcag_version` | `str` | `"2.0"` / `"2.1"` / `"2.2"` (lowest version the SC is in) |
| `section508` | `bool` | True when the SC is in the 508 floor (WCAG 2.0 A/AA) |
| `category` | `str` | grouping, e.g. `"images"`, `"structure"`, `"color"`, `"links"`, `"media"`, `"motion"`, `"document"` |
| `fixable` | `bool` | can `export` apply a fix for this? |
| `fix_action` | `str \| None` | applier verb, e.g. `"set_alt_text"`, `"mark_decorative"`, `"set_title"`, `"set_link_text"`, `"set_table_header"`, `"apply_contrast_color"`, `"bump_font_size"`, `"set_doc_title"`, `"set_doc_language"` |
| `current_value` | `str \| None` | offending value (text snippet, color hex, size…) |
| `suggested_value` | `str \| None` | AI/deterministic draft the user can accept/edit |
| `target` | `dict` | stable locator the export resolver uses (see below) |

**Target locator** (JSON-serializable, stable across analyze→export for the same bytes):
- shape-level: `{"slide": i, "shape_id": id}`
- run-level: `{"slide": i, "shape_id": id, "para": p, "run": r}`
- document-level: `{"scope": "document", "field": "title"|"language"}`

A reverse resolver `resolve_target(prs, target) -> shape|run|prs` locates the live element in a freshly-opened deck. The existing `refs.shape_ref` string stays as the human-readable id.

## Standards + scoring

A static module encodes the **applicable success criteria** for a static deck (~20 SCs from the research: 1.1.1, 1.2.x, 1.3.1, 1.3.2, 1.3.3, 1.4.1, 1.4.3, 1.4.5, 1.4.11, 2.2.2, 2.3.1, 2.4.2, 2.4.4, 2.4.6, 3.1.1, plus conditional 2.5.x/4.1.2 marked N/A-for-static). Each carries its number, title, level (A/AA), version, and 508 membership.

- **Coverage matrix**: for each applicable SC → status `PASS` / `FAIL` / `NEEDS_REVIEW` / `N_A`, derived from findings (a FAIL if any open finding maps to it; NEEDS_REVIEW for criteria the tool can only flag for human judgment — color-alone, captions-presence, reading-order-correctness; N_A for interactive-only SCs on a static deck; else PASS). **A NEEDS_REVIEW item must never read as PASS.**
- **Score**: deterministic 0–100. Errors weigh more than warnings; NEEDS_REVIEW items are surfaced but don't silently inflate the number. A letter grade (A–F) from the score. Recomputable **client-side** as issues are accepted so the score climbs live.
- **Honest framing**: each finding tagged `508 = WCAG 2.0 A/AA (legal floor today)` vs `2.1/2.2 AA (best practice)`. Never check the obsoleted 4.1.1 Parsing.

## Fix appliers (export phase — deterministic, AI-free)

A registry keyed by `fix_action`. Each `apply(prs, target, value) -> bool`. Reuses existing mutation patterns; adds new ones (all verified low-risk in the engine map):

| action | mutation |
|---|---|
| `set_alt_text` | `shape._element._nvXxPr.cNvPr.set("descr", value)` |
| `mark_decorative` | add `<adec:decorative val="1">` under `cNvPr` |
| `set_title` | `slide.shapes.title.text = value` |
| `set_doc_title` / `set_doc_language` | `prs.core_properties.title/language = value` |
| `set_link_text` | set `run.text = value`, preserving `run.hyperlink.address` |
| `set_table_header` | `shape.table.first_row = True` |
| `apply_contrast_color` | `run.font.color.rgb = RGBColor(*value)` (explicit-color runs only) |
| `bump_font_size` | `run.font.size = Pt(max(18, current))` |

Appliers are pure/deterministic and **only touch targets in the approved plan** — un-accepted issues are left untouched. Originals are never modified (export writes a new deck).

## AI suggestions (analyze phase)

Reuse the `Describer` (Claude). In `analyze`, generate `suggested_value` for: alt text (vision, per raster image), slide titles (from slide text), link text (from URL + context). Bounded by `CappedDescriber` / `SLIDECHECK_MAX_AI_IMAGES`. Every AI draft is labeled **machine-generated — review this** (mirrors MS Intelligent Services). Degrades gracefully to no-suggestion when no key (the upgrade still works without AI — issues are still detected, scored, and manually fixable).

## New checks (P0, additive)

From the research's highest-value automatable gaps:
- **2.2.2 / 1.4.2 / 2.3.1** — auto-advance / autoplay / flashing: parse slide-transition `advTm` (advance-after timing), autoplay media, looping/fast animations → warn; auto-advance optionally fixable (remove timing).
- **1.3.3 Sensory characteristics** — text scan for sensory-only instructions ("the green button on the right", "see below").
- **1.4.1 Use of color** — hyperlinks styled by color without underline; color-as-meaning phrasing.
- **2.4.6 Generic / duplicate titles** — extend `slide_titles`: flag generic ("Slide 1", "Untitled") and cross-slide duplicate titles.

## Interactive UI (rewrite `public/`)

Vanilla HTML/CSS/JS (no build step), but a real product UI (use the frontend-design skill for a distinctive, professional, *accessible* look — it's an accessibility tool):
- **Header**: big score dial + letter grade + "X issues to fix".
- **Coverage matrix** (collapsible): every applicable SC with PASS/FAIL/NEEDS-REVIEW/N-A + version badge.
- **Worklist**: issue cards grouped by slide. Each card: category icon, plain-language explanation, **SC + version badge**, the offending value (inline **thumbnail of the real embedded image** for alt-text/decorative; text snippet otherwise), an **editable suggestion textarea**, and **Accept / Edit / Skip** controls. Accepting updates the live score and adds to the fix-plan.
- **Export bar**: "Download fixed PowerPoint" (sends original + plan to `/api/export`) + "Download report".
- **Security**: render every server-derived string via `textContent` / `esc` — **never `innerHTML`** for untrusted data (no sandboxed iframe needed now; the report iframe is gone from the interactive view).

## Error handling / robustness

- Password gate (503 unconfigured / 401 wrong) and per-file isolation preserved.
- `analyze` on a corrupt deck → friendly per-file error (engine already guards).
- Missing/failed AI key → suggestions absent, everything else works.
- `export` validates the plan, ignores unresolvable targets safely, never raises a 500 for one bad item.
- Upload size cap (`SLIDECHECK_MAX_UPLOAD_MB`) applies to both endpoints; export re-sends the original (bytes doubled only on the single export action).

## Testing

- **Keep all 93 existing tests green** (CLI/GUI/`process_file` unchanged).
- Engine: each new check; each fix applier round-trips on real OOXML (and leaves un-targeted content untouched); score determinism; coverage-matrix logic; target resolver.
- Web: `analyze` returns the expected JSON shape (findings + score + matrix + thumbnails); `export` applies a plan and the result re-opens as a valid `.pptx` with exactly the approved changes; analyze→export round-trip; password/validation paths.
- E2E: live Playwright run after deploy (upload → worklist → accept a fix → export → valid deck).

## Deferred (P1/P2 — explicitly out of scope this round)

LibreOffice full-slide thumbnails (image bloat + cold-start risk; the inline embedded-image thumbnail covers ~80% at zero cost); table complex-structure, list semantics, reading-order spatial heuristic; media caption-track parsing; section names; images-of-text OCR; non-text contrast; WCAG 2.2 interactive SCs; structural placeholder-usage check. Tracked for a fast-follow.

## Success criteria

1. A non-technical user uploads a deck and gets a score + grade + plain-language issue worklist (not a static report).
2. For each fixable issue she can accept/edit an AI or deterministic suggestion; the score updates live.
3. One click downloads a deck with **exactly** the approved fixes applied; the original is never modified; nothing persists server-side.
4. The coverage matrix honestly shows every applicable SC's status (PASS/FAIL/NEEDS-REVIEW/N-A) with version tags; nothing unverified reads as PASS.
5. CLI, desktop GUI, and all prior tests still pass; the app stays deployable on Fly and is redeployed + verified live.

## Build order (deployable milestones)

Core interactive flow first (ships the visible leap even if new checks slip):
1. Extended `Finding` model + standards metadata on existing checks.
2. Target resolver + fix-applier registry (wrap existing + add new appliers).
3. Standards/score/coverage module.
4. `analyze` service (findings + AI suggestions + score + matrix + thumbnails).
5. `export` service (apply plan → fixed deck + report).
6. `/api/analyze` + `/api/export` endpoints.
7. Interactive front-end rewrite.
8. New checks (auto-advance/flash, sensory, use-of-color, generic/duplicate titles) — additive.
9. Deploy to Fly + live verify.
