# SlideCheck Interactive Remediation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` checkboxes. TDD throughout.

**Goal:** Turn SlideCheck from a static report into an interactive remediation studio: analyze → guided per-issue worklist with AI suggestions (Accept/Edit/Skip) + live score → export a deck with exactly the approved fixes. Stateless two-phase API; engine reused; CLI/GUI untouched.

**Architecture:** `POST /api/analyze` returns structured findings + AI suggestions + score + coverage matrix (no save, no deck returned). Browser builds a fix-plan. `POST /api/export` takes original + plan, applies fixes deterministically, returns fixed deck + report. New interactive front end. See spec: `docs/superpowers/specs/2026-06-25-slidecheck-interactive-remediation-design.md`.

**Tech Stack:** Python 3.12 / uv, python-pptx, Pillow, anthropic, FastAPI; vanilla HTML/CSS/JS; Fly.io.

## Global Constraints

- Python `>=3.12`; use **uv** (`uv run pytest`, `uv add`) — never bare pip/python.
- **Do NOT change `pipeline.process_file` behavior** — CLI, Tkinter GUI, and all 93 existing tests must keep passing. The interactive flow is a NEW layer over the same `checks`/`fixers`/helpers.
- **Originals never modified**; nothing persists server-side (temp/in-memory only).
- Web runtime excludes `tkinterdnd2`. Env limits read at request time. Password gate preserved (503 unset / 401 wrong).
- **Front end: render every server-derived string via `textContent`/`esc` — never `innerHTML` for untrusted data.**
- Every AI-generated value is labeled machine-generated. NEEDS_REVIEW must never read as PASS. Never implement WCAG 4.1.1 (obsoleted).
- Backward-compatible `Finding` changes only (new fields get defaults) so existing checks/report keep working.

---

### Task 1: Extend the `Finding` model with standards + remediation metadata

**Files:**
- Modify: `pptx_a11y/models.py`
- Test: `tests/test_models.py`

**Interfaces — Produces:** `Finding` gains fields (all defaulted, backward-compatible):
```python
sc_refs: list[str] = field(default_factory=list)
wcag_version: str = ""          # "2.0" | "2.1" | "2.2" | ""
section508: bool = False
category: str = ""              # images|structure|color|links|media|motion|document|text
fixable: bool = False
fix_action: str | None = None
current_value: str | None = None
suggested_value: str | None = None
target: dict = field(default_factory=dict)
```

- [ ] **Step 1: Failing test** — add to `tests/test_models.py`:
```python
def test_finding_has_remediation_fields_with_defaults():
    from pptx_a11y.models import Finding, Severity
    f = Finding(check_id="x", severity=Severity.ERROR, slide_index=0, message="m")
    assert f.sc_refs == [] and f.wcag_version == "" and f.section508 is False
    assert f.category == "" and f.fixable is False and f.fix_action is None
    assert f.current_value is None and f.suggested_value is None and f.target == {}

def test_finding_accepts_remediation_fields():
    from pptx_a11y.models import Finding, Severity
    f = Finding(check_id="alt_text", severity=Severity.ERROR, slide_index=1, message="m",
                sc_refs=["1.1.1"], wcag_version="2.0", section508=True, category="images",
                fixable=True, fix_action="set_alt_text", current_value="", suggested_value="A chart",
                target={"slide": 1, "shape_id": 5})
    assert f.fix_action == "set_alt_text" and f.target["shape_id"] == 5
```
- [ ] **Step 2:** Run `uv run pytest tests/test_models.py -v` → FAIL.
- [ ] **Step 3:** Add the fields to the `Finding` dataclass (after `auto_fixed`). Keep `Change` as-is.
- [ ] **Step 4:** `uv run pytest tests/test_models.py -v` → PASS.
- [ ] **Step 5:** `uv run pytest -q` → all green (defaults keep existing checks/report working).
- [ ] **Step 6:** Commit `feat(model): standards + remediation metadata on Finding`.

---

### Task 2: Standards catalog, scoring, and coverage matrix

**Files:**
- Create: `pptx_a11y/standards.py`
- Test: `tests/test_standards.py`

**Interfaces — Produces:**
- `SC_CATALOG: dict[str, dict]` — keyed by SC number; each `{"title": str, "level": "A"|"AA", "version": "2.0"|"2.1"|"2.2", "section508": bool, "static_applicable": bool}`. Include at least: 1.1.1, 1.2.2, 1.3.1, 1.3.2, 1.3.3, 1.4.1, 1.4.3, 1.4.5, 1.4.11, 2.2.2, 2.3.1, 2.4.2, 2.4.4, 2.4.6, 3.1.1 (static_applicable True); 2.4.11, 2.5.7, 2.5.8, 3.3.8, 4.1.2 (static_applicable False → N_A). 508 floor = WCAG 2.0 A/AA members.
- `NEEDS_REVIEW_SC: set[str]` — SCs the tool can only flag for human judgment: `{"1.4.1","1.2.2","1.3.2","1.4.5","1.4.11","2.3.1"}`.
- `score(findings: list[Finding]) -> dict` → `{"score": int 0-100, "grade": "A".."F", "errors": int, "warnings": int, "needs_review": int, "fixable": int}`. Deterministic: start 100; subtract per OPEN (not auto_fixed/accepted) finding — ERROR −8, WARNING −3, INFO −1; floor 0. Grade: ≥95 A, ≥85 B, ≥70 C, ≥55 D, else F.
- `coverage_matrix(findings) -> list[dict]` → one row per `static_applicable` SC: `{"sc": "1.1.1", "title":..., "level":..., "version":..., "section508":..., "status": "PASS"|"FAIL"|"NEEDS_REVIEW"|"N_A"}`. FAIL if any open finding lists the SC in `sc_refs`; else NEEDS_REVIEW if SC in `NEEDS_REVIEW_SC` AND some finding/condition flags it for review; else PASS. Non-`static_applicable` SCs → status `N_A`. Order by SC number.

- [ ] **Step 1: Failing tests** — `tests/test_standards.py`:
```python
from pptx_a11y.models import Finding, Severity
from pptx_a11y.standards import score, coverage_matrix, SC_CATALOG

def _f(check, sev, scs, fixed=False):
    return Finding(check_id=check, severity=sev, slide_index=0, message="m",
                   sc_refs=scs, auto_fixed=fixed)

def test_score_perfect_when_no_open_findings():
    assert score([])["score"] == 100
    assert score([])["grade"] == "A"

def test_score_subtracts_by_severity_and_ignores_fixed():
    s = score([_f("a", Severity.ERROR, ["1.1.1"]), _f("b", Severity.WARNING, ["1.4.3"]),
               _f("c", Severity.ERROR, ["2.4.2"], fixed=True)])
    assert s["score"] == 100 - 8 - 3   # the fixed error is ignored
    assert s["errors"] == 1 and s["warnings"] == 1

def test_coverage_matrix_marks_fail_for_open_sc_and_na_for_interactive():
    rows = {r["sc"]: r for r in coverage_matrix([_f("a", Severity.ERROR, ["1.1.1"])])}
    assert rows["1.1.1"]["status"] == "FAIL"
    assert rows["2.4.2"]["status"] == "PASS"       # applicable, no open finding
    assert rows["2.5.8"]["status"] == "N_A"        # interactive-only
    assert rows["1.1.1"]["section508"] is True

def test_catalog_has_versions_and_levels():
    assert SC_CATALOG["1.4.3"]["version"] == "2.0" and SC_CATALOG["1.4.3"]["level"] == "AA"
    assert SC_CATALOG["1.4.11"]["version"] == "2.1"
```
- [ ] **Step 2:** Run → FAIL (module missing).
- [ ] **Step 3:** Implement `standards.py` per the interface. (508 membership: all 2.0 A/AA SCs = True; 2.1/2.2 = False.)
- [ ] **Step 4:** `uv run pytest tests/test_standards.py -v` → PASS.
- [ ] **Step 5:** Commit `feat(standards): SC catalog, deterministic score, coverage matrix`.

---

### Task 3: Target locator on findings + reverse resolver

**Files:**
- Modify: `pptx_a11y/refs.py` (add `resolve_target`)
- Modify: existing checks to populate `target` + standards metadata where cheap (at minimum: alt_text, slide_titles, metadata, contrast, font_size, link_text, tables — set `sc_refs`, `wcag_version`, `section508`, `category`, `fixable`, `fix_action`, `current_value`, `target`).
- Test: `tests/test_refs.py`, and update `tests/checks/*` as needed.

**Interfaces — Produces:**
- `resolve_target(prs, target: dict)` → returns the live `shape`, `run`, or the `prs` (for document scope), or `None` if unresolvable. Uses `target["slide"]`, `target["shape_id"]` (match `shape.shape_id`), optional `target["para"]`/`target["run"]` indices into the shape's text frame; `{"scope":"document"}` → `prs`.
- Helper `shape_target(slide_index, shape) -> dict` and `run_target(slide_index, shape, p, r) -> dict` for checks to emit stable targets.

- [ ] **Step 1: Failing test** — `tests/test_refs.py`:
```python
from pptx import Presentation
from pptx_a11y.refs import resolve_target, shape_target
from tests.fixtures.build import deck_with_issues

def test_resolve_shape_target_roundtrip(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path/"d.pptx")))
    slide0 = prs.slides[0]
    pic = next(s for s in slide0.shapes if s.shape_type == 13)  # PICTURE
    t = shape_target(0, pic)
    got = resolve_target(prs, t)
    assert got is not None and got.shape_id == pic.shape_id

def test_resolve_document_scope(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path/"d.pptx")))
    assert resolve_target(prs, {"scope": "document"}) is prs

def test_resolve_unknown_returns_none(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path/"d.pptx")))
    assert resolve_target(prs, {"slide": 0, "shape_id": 999999}) is None
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `resolve_target` + `shape_target`/`run_target`. For run resolution, walk `shape.text_frame.paragraphs[p].runs[r]` guarding IndexError → None.
- [ ] **Step 4:** Update each listed check to populate the new metadata (use `SC_CATALOG`-consistent values; set `fixable=True`+`fix_action` for: alt_text→`set_alt_text`, slide_title→`set_title`, metadata→`set_doc_title`/`set_doc_language`, contrast→`apply_contrast_color`, font_size→`bump_font_size`, link_text→`set_link_text`, table(no-header)→`set_table_header`; reading_order/media→`fixable=False`). Keep `message`/`suggestion` text intact so existing check tests pass (adjust assertions only if they check new fields).
- [ ] **Step 5:** `uv run pytest -q` → green (fix any check tests that need new-field assertions).
- [ ] **Step 6:** Commit `feat(engine): target resolver + standards metadata on checks`.

---

### Task 4: Fix-applier registry (deterministic export-phase fixes)

**Files:**
- Create: `pptx_a11y/appliers.py`
- Test: `tests/test_appliers.py`

**Interfaces — Produces:**
- `APPLIERS: dict[str, callable]` mapping `fix_action` → `apply(prs, target: dict, value) -> bool` (True if applied). Implement: `set_alt_text`, `mark_decorative`, `set_title`, `set_doc_title`, `set_doc_language`, `set_link_text`, `set_table_header`, `apply_contrast_color` (value = `[r,g,b]`), `bump_font_size` (value = int pt, min 18), `remove_auto_advance`.
- `apply_plan(prs, plan: list[dict]) -> list[dict]` → for each `{target, action, value}` resolve+apply via `APPLIERS`, collecting `{action, ok: bool}`. Never raises on one bad item (guard each).

Use the exact mutations from the engine map (e.g. `set_alt_text`: `shape._element._nvXxPr.cNvPr.set("descr", value)`; `set_table_header`: `shape.table.first_row = True`; `mark_decorative`: add `<adec:decorative val="1">`; `apply_contrast_color`: `run.font.color.rgb = RGBColor(*value)`; `bump_font_size`: `run.font.size = Pt(max(18,int(value)))`; `set_link_text`: `run.text = value`).

- [ ] **Step 1: Failing tests** — `tests/test_appliers.py` (build small decks via `tests/fixtures/build.py`; assert each mutation took effect by re-reading the element, e.g. alt text set → `cNvPr.get("descr") == value`; table header → `table.first_row is True`; font bumped → `run.font.size.pt >= 18`). Include `test_apply_plan_skips_unresolvable_target_without_raising`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement appliers + `apply_plan`.
- [ ] **Step 4:** `uv run pytest tests/test_appliers.py -v` → PASS. Then `uv run pytest -q`.
- [ ] **Step 5:** Commit `feat(engine): deterministic fix-applier registry + apply_plan`.

---

### Task 5: Analyze engine + AI suggestion generation

**Files:**
- Create: `pptx_a11y/analyze.py`
- Test: `tests/test_analyze.py`

**Interfaces — Produces:**
- `run_checks(prs) -> list[Finding]` (imports + runs `checks.load_all()`; idempotent — does NOT mutate the deck).
- `generate_suggestions(prs, findings, describer) -> None` (mutates findings in place): for `set_alt_text` findings with a resolvable PICTURE target → `describer.describe(...)`; for `set_title` → `describer.suggest_text(...)`; for `set_link_text` → `describer.suggest_text(...)` from the URL+context; sets `finding.suggested_value` (None on failure). Bounded by the passed describer (caller wraps in `CappedDescriber`). Deterministic suggestions (font bump→"18", table header→n/a, contrast→hex from `suggest_compliant_color`) are filled here too where no AI is needed.
- `analyze(prs, describer) -> dict` → `{"findings": [finding_to_dict(f)...], "score": score(...), "coverage": coverage_matrix(...)}`. `finding_to_dict` serializes all Finding fields (JSON-safe).

- [ ] **Step 1: Failing tests** — `tests/test_analyze.py`: with `NullDescriber`, `analyze(prs, NullDescriber())` returns a dict with `findings` (list of dicts containing `sc_refs`, `fix_action`, `target`), `score` (dict), `coverage` (list). Assert deterministic suggestions present (e.g. a contrast finding gets a hex `suggested_value`) and that AI-only suggestions are None under NullDescriber. `run_checks` returns findings without changing the deck (save bytes equal before/after).
- [ ] **Step 2-4:** RED → implement → GREEN → `uv run pytest -q`.
- [ ] **Step 5:** Commit `feat(engine): analyze() — checks + AI/deterministic suggestions + score + coverage`.

---

### Task 6: Web analyze + export services (stateless)

**Files:**
- Create: `pptx_a11y/web/analyze_service.py`, `pptx_a11y/web/export_service.py`
- Test: `tests/web/test_analyze_service.py`, `tests/web/test_export_service.py`

**Interfaces — Produces:**
- `analyze_upload(filename, data: bytes, describer) -> dict`: open bytes in a temp dir, `analyze(prs, describer)`, also attach per-finding `thumbnail` (base64 PNG, max ~160px) for `set_alt_text`/`mark_decorative` findings via `imageutil.image_bytes_and_type` + Pillow resize; return `{"filename", "error", "analysis": {...}}`. Ephemeral (temp dir removed).
- `export_with_plan(filename, data: bytes, plan: list[dict]) -> dict`: open bytes, `appliers.apply_plan(prs, plan)`, save to temp, read fixed bytes, render a final report (reuse/extend `html_report` or a new compliance report), return `{"filename","error","fixed_filename","fixed_bytes","report_html","applied": [...]}`. Original never modified; nothing persists.

- [ ] **Step 1: Failing tests** — analyze service returns analysis dict with findings + a base64 `thumbnail` on the alt-text finding (built from `deck_with_issues` which has a picture). Export service: given a plan `[{target: <pic target>, action: "set_alt_text", value: "A red square"}]`, the returned `fixed_bytes` re-opens and the picture's `descr` == "A red square", and an un-targeted finding's element is unchanged.
- [ ] **Step 2-4:** RED → implement → GREEN → `uv run pytest -q`.
- [ ] **Step 5:** Commit `feat(web): stateless analyze + export services`.

---

### Task 7: `/api/analyze` + `/api/export` endpoints

**Files:**
- Modify: `api/index.py` (add the two endpoints; keep password gate + size cap + per-file isolation; remove `/api/process` and the old StaticFiles report path is unaffected). Keep `GET /api/health`.
- Test: `tests/web/test_api.py` (extend)

**Interfaces — Produces:**
- `POST /api/analyze` (multipart, field `files`, header `x-slidecheck-password`) → `{"files": [analyze_upload(...) per file]}`. Builds `CappedDescriber(get_describer({}), _max_ai_images())` per request.
- `POST /api/export` (multipart: field `files` = the original .pptx, field `plan` = JSON string of the fix-plan, password header) → `{"files":[export_with_plan(...)]}` with `fixed_pptx_b64`. Validates plan is a JSON list; bad plan → 400.
- Status codes unchanged (503/401/400/413). Update existing `/api/process` tests to the new endpoints.

- [ ] **Step 1: Failing tests** — `test_analyze_happy_path` (200, JSON has `files[0].analysis.findings/score/coverage`), `test_analyze_requires_password` (401), `test_export_applies_plan` (POST original + a plan → 200, decode `fixed_pptx_b64` → valid pptx with the change), `test_export_bad_plan_400`.
- [ ] **Step 2-4:** RED → implement → GREEN → `uv run pytest -q` (pristine).
- [ ] **Step 5:** Commit `feat(api): stateless /api/analyze + /api/export`.

---

### Task 8: Interactive remediation front end

**Files:**
- Rewrite: `public/index.html`, `public/styles.css`, `public/app.js`

**Behavior:** password gate (reuse) → upload → `POST /api/analyze` → render: score dial + grade + issue count; collapsible coverage matrix (SC, level, version badge, status pill); worklist of issue cards grouped by slide. Each fixable card: plain-language explanation, SC+version badge, offending value (inline `<img>` from base64 `thumbnail` for image issues; text snippet otherwise), editable suggestion `<textarea>` prefilled with `suggested_value`, **Accept / Edit / Skip**. Accept adds `{target, action, value}` to the in-memory plan and updates the live score (recompute client-side: re-add the finding's severity weight). Export bar: "Download fixed PowerPoint" → `POST /api/export` with the original File + `plan` JSON → Blob download; "Download report" from returned `report_html`. **All server strings via `textContent`/`esc`; never `innerHTML` for untrusted data.** Use the frontend-design skill for a polished, accessible visual design (good contrast, keyboard-operable, ARIA roles, focus management).

- [ ] **Step 1:** Write the three files.
- [ ] **Step 2:** `node --check public/app.js`; `uv run pytest -q` still green (StaticFiles mount).
- [ ] **Step 3:** Commit `feat(web): interactive remediation front end`.
- [ ] **Step 4:** (Controller runs the live Playwright e2e after deploy.)

---

### Task 9: New P0 checks (additive)

**Files:**
- Create: `pptx_a11y/checks/motion.py` (2.2.2/1.4.2/2.3.1 — auto-advance/autoplay/flash), `pptx_a11y/checks/sensory.py` (1.3.3), `pptx_a11y/checks/use_of_color.py` (1.4.1). Extend `pptx_a11y/checks/slide_titles.py` for generic/duplicate (2.4.6).
- Register in `checks/__init__.py` load tuple. Add `remove_auto_advance` to `_FIX_MAP` if auto-advance is made fixable.
- Tests: `tests/checks/test_motion.py`, `test_sensory.py`, `test_use_of_color.py`, extend `test_slide_titles.py`.

**Detection (from research):**
- **motion**: slide auto-advance via `<p:transition>` with `advTm` / `advClick="0"` (parse `slide._element` transition); autoplay media; warn. Auto-advance → `fixable=True`, `fix_action="remove_auto_advance"`.
- **sensory** (1.3.3): regex scan run text for sensory-only instruction patterns (`\b(left|right|above|below|the (red|green|blue) (one|button)|round|square|shown (here|below|above))\b` in an instructional context) → WARNING, not auto-fixable, AI-assist rephrase.
- **use_of_color** (1.4.1): hyperlinked run whose font has no underline (`run.font.underline` falsy) → "link distinguished by color only" WARNING; partial fix = add underline (optional applier `add_link_underline`).
- **slide_titles** generic/duplicate (2.4.6): title matching `^(slide ?\d*|untitled|title)$` (case-insensitive) → generic WARNING; titles duplicated across slides → duplicate WARNING. Both `fixable` via `set_title`.

- [ ] **Step 1-4 per check:** RED tests (build decks exercising each) → implement → GREEN. Wire registration.
- [ ] **Step 5:** `uv run pytest -q` all green.
- [ ] **Step 6:** Commit `feat(checks): motion/sensory/use-of-color/title-quality (WCAG 2.2.2/1.3.3/1.4.1/2.4.6)`.

---

### Task 10: Deploy + live verification

- [ ] **Step 1:** `uv run pytest -q` green; merge the branch to `main` (per repo pattern).
- [ ] **Step 2:** Local Docker smoke test (build image, run container, hit `/api/health`, `/api/analyze` with a fixture + password → findings JSON, `/api/export` with a plan → valid pptx).
- [ ] **Step 3:** `fly deploy --app slidecheck-a11y`.
- [ ] **Step 4:** Live Playwright e2e: open the URL, enter password `accessible`, upload a fixture deck, accept a fix, export, confirm a valid downloaded deck; confirm the score + coverage matrix render; console clean.
- [ ] **Step 5:** Commit any deploy-config tweaks. Update README + memory.

## Self-Review

- Spec coverage: two-phase API (T6/T7), Finding model (T1), score+matrix (T2), target+appliers (T3/T4), analyze+suggestions (T5), interactive UI (T8), new checks (T9), deploy (T10). ✓
- `process_file`/CLI/GUI untouched; new layer single-sources `checks`/`fixers`/helpers. ✓
- Security: appliers guard per-item; front end `textContent`-only; password gate preserved. ✓
- Honest standards: NEEDS_REVIEW never PASS; 508 vs 2.1/2.2 tagged; no 4.1.1. ✓
- If time-constrained, T1–T8 (core flow) ship the visible leap; T9 is additive. ✓
