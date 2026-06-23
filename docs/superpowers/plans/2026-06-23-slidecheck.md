# SlideCheck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A drag-and-drop desktop tool that scans `.pptx` files for WCAG 2.1 AA + Section 508 accessibility issues, auto-fixes what is safe, and produces a clear report — never modifying the original.

**Architecture:** A headless, fully-tested engine (`pptx_a11y`) of independent check and fixer modules driven by a single pipeline, wrapped by a thin CLI (for batch + tests) and a thin Tkinter drag-drop GUI. AI alt-text is injected as a `Describer` so the engine stays deterministic and testable; the real Claude implementation is mocked in tests.

**Tech Stack:** Python 3.12 (managed with **uv**), python-pptx, Pillow, anthropic, tkinterdnd2, pytest, pyinstaller.

## Global Constraints

- **Python 3.12**, managed exclusively with **uv** (`uv run`, `uv add`, `uv sync`) — never bare `pip`/`python`.
- **Standard:** WCAG 2.1 AA + Section 508.
- **Originals are never modified.** Output for `deck.pptx` is `deck_accessible.pptx` + `deck_a11y_report.html` + `deck_a11y_report.json`, written alongside the source. If an output name exists, disambiguate (`_accessible_1`), never clobber.
- **Per-file isolation:** a corrupt/unreadable file yields a `FileResult` with `error` set; batches continue.
- **Graceful AI degradation:** with no API key or an unreachable API, alt-text generation is skipped and missing alt text is reported as an `ERROR` finding (flag-only) — the run never fails for this reason.
- **Default thresholds:** contrast 4.5:1 (3:1 for large text ≥ 18pt or ≥ 14pt bold); minimum body font 18pt.
- **Alt-text XML API (verified):** read/write via `shape._element._nvXxPr.cNvPr.get("descr")` / `.set("descr", value)`.
- **Claude model for vision:** `claude-sonnet-4-6`.
- Machine-generated fixes (AI alt text, AI titles) set `Change.machine_generated = True` and are visually flagged "review this" in the report.

---

### Task 1: Project scaffold + core data model

**Files:**
- Create: `pyproject.toml`, `pptx_a11y/__init__.py`, `pptx_a11y/models.py`, `pptx_a11y/refs.py`, `tests/__init__.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Severity` (enum: `ERROR`/`WARNING`/`INFO`), `Finding`, `Change`, `FileResult` dataclasses; `shape_ref(slide_index: int, shape) -> str`.

- [ ] **Step 1: Initialize the uv project and dependencies**

Run:
```bash
cd ~/Documents/slidecheck
uv init --package --name slidecheck --python 3.12 .
uv add python-pptx Pillow anthropic tkinterdnd2
uv add --dev pytest
```
(If `uv init` complains the dir is non-empty, run `uv init --package --name slidecheck --python 3.12 --bare .` then create `pptx_a11y/__init__.py` by hand.)

- [ ] **Step 2: Write the failing test**

`tests/test_models.py`:
```python
from pptx_a11y.models import Severity, Finding, Change, FileResult
from pptx_a11y.refs import shape_ref


def test_finding_defaults():
    f = Finding(check_id="alt_text", severity=Severity.ERROR, slide_index=0, message="x")
    assert f.shape_ref is None
    assert f.auto_fixed is False
    assert f.severity.value == "error"


def test_change_machine_generated_flag():
    c = Change(fixer_id="alt_text", slide_index=1, description="added", machine_generated=True)
    assert c.machine_generated is True


def test_file_result_collections_default_empty():
    r = FileResult(source_path="a.pptx")
    assert r.findings == [] and r.changes == [] and r.error is None


class _FakeShape:
    shape_id = 7


def test_shape_ref_is_stable_string():
    assert shape_ref(2, _FakeShape()) == "slide2:shape7"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: pptx_a11y.models`).

- [ ] **Step 4: Implement the model and refs**

`pptx_a11y/models.py`:
```python
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    check_id: str
    severity: Severity
    slide_index: int
    message: str
    shape_ref: str | None = None
    suggestion: str | None = None
    auto_fixed: bool = False


@dataclass
class Change:
    fixer_id: str
    slide_index: int
    description: str
    shape_ref: str | None = None
    machine_generated: bool = False


@dataclass
class FileResult:
    source_path: str
    output_path: str | None = None
    findings: list[Finding] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    error: str | None = None
```

`pptx_a11y/refs.py`:
```python
def shape_ref(slide_index: int, shape) -> str:
    """Stable, human-readable reference for a shape within a slide."""
    return f"slide{slide_index}:shape{shape.shape_id}"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock pptx_a11y tests
git commit -m "feat: project scaffold and core data model"
```

---

### Task 2: Fixture builder + loader

**Files:**
- Create: `tests/fixtures/__init__.py` (fixture-building helpers), `pptx_a11y/loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_presentation(path: str) -> Presentation` (raises `LoadError` on failure); `tests/fixtures/build.py` helpers `clean_deck()`, `deck_with_issues()` returning saved `.pptx` paths in a tmp dir.

- [ ] **Step 1: Write the fixture builders (test support, not a test yet)**

`tests/fixtures/build.py`:
```python
import base64
import io
from pptx import Presentation
from pptx.util import Inches, Pt

# 1x1 red PNG
_RED_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _add_picture(slide, alt: str | None):
    pic = slide.shapes.add_picture(io.BytesIO(_RED_PNG), Inches(1), Inches(1), Inches(1), Inches(1))
    if alt is not None:
        pic._element._nvXxPr.cNvPr.set("descr", alt)
    return pic


def clean_deck(path: str) -> str:
    """A deck with no accessibility issues."""
    prs = Presentation()
    prs.core_properties.title = "Clean Deck"
    s = prs.slides.add_slide(prs.slide_layouts[5])  # title only
    s.shapes.title.text = "Intro"
    _add_picture(s, "A red square")
    prs.save(path)
    return path


def deck_with_issues(path: str) -> str:
    """A deck planted with one of each issue the checks target."""
    prs = Presentation()
    # slide 0: missing title + picture with no alt text
    s0 = prs.slides.add_slide(prs.slide_layouts[5])
    s0.shapes.title.text = ""           # missing title
    _add_picture(s0, None)              # missing alt text
    # slide 1: tiny font + bad link text
    s1 = prs.slides.add_slide(prs.slide_layouts[5])
    s1.shapes.title.text = "Details"
    tb = s1.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1)).text_frame
    run = tb.paragraphs[0].add_run()
    run.text = "click here"
    run.font.size = Pt(10)             # too small
    r = run._r
    # add a hyperlink so link_text check sees it
    run.hyperlink.address = "https://example.com"
    prs.save(path)
    return path
```

- [ ] **Step 2: Write the failing loader test**

`tests/test_loader.py`:
```python
import os
from pptx import Presentation
import pytest
from pptx_a11y.loader import load_presentation, LoadError
from tests.fixtures.build import clean_deck


def test_loads_valid_pptx(tmp_path):
    p = clean_deck(str(tmp_path / "ok.pptx"))
    prs = load_presentation(p)
    assert isinstance(prs, Presentation().__class__)
    assert len(prs.slides) == 1


def test_corrupt_file_raises_loaderror(tmp_path):
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"not a real pptx")
    with pytest.raises(LoadError):
        load_presentation(str(bad))


def test_missing_file_raises_loaderror():
    with pytest.raises(LoadError):
        load_presentation("/nonexistent/no.pptx")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_loader.py -v`
Expected: FAIL (`ModuleNotFoundError: pptx_a11y.loader`).

- [ ] **Step 4: Implement the loader**

`pptx_a11y/loader.py`:
```python
from pptx import Presentation


class LoadError(Exception):
    """Raised when a .pptx cannot be opened (missing, corrupt, or not a pptx)."""


def load_presentation(path: str):
    try:
        return Presentation(path)
    except Exception as exc:  # noqa: BLE001 - any open failure is a load failure
        raise LoadError(f"Could not open {path}: {exc}") from exc
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_loader.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add pptx_a11y/loader.py tests/test_loader.py tests/fixtures
git commit -m "feat: pptx loader with corrupt-file isolation and test fixtures"
```

---

### Task 3: Alt-text check

**Files:**
- Create: `pptx_a11y/checks/__init__.py`, `pptx_a11y/checks/alt_text.py`
- Test: `tests/checks/test_alt_text.py`, `tests/checks/__init__.py`

**Interfaces:**
- Consumes: `Finding`, `Severity`, `shape_ref`.
- Produces: `check(prs) -> list[Finding]` with `check_id="alt_text"`; `pptx_a11y/checks/__init__.py` exposes a growing `ALL_CHECKS: list[Callable[[Presentation], list[Finding]]]`. Helper `iter_shapes(prs)` yielding `(slide_index, shape)` for all shapes including those in groups.

- [ ] **Step 1: Write the failing test**

`tests/checks/test_alt_text.py`:
```python
from pptx_a11y.checks.alt_text import check
from tests.fixtures.build import clean_deck, deck_with_issues
from pptx import Presentation


def test_flags_picture_without_alt_text(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.check_id == "alt_text" and f.slide_index == 0 for f in findings)
    assert findings[0].severity.value == "error"


def test_clean_deck_has_no_alt_text_findings(tmp_path):
    prs = Presentation(clean_deck(str(tmp_path / "ok.pptx")))
    assert check(prs) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/checks/test_alt_text.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the shape iterator and check**

`pptx_a11y/checks/__init__.py`:
```python
from pptx.enum.shapes import MSO_SHAPE_TYPE


def iter_shapes(prs):
    """Yield (slide_index, shape) for every shape, descending into groups."""
    for i, slide in enumerate(prs.slides):
        yield from _walk(i, slide.shapes)


def _walk(slide_index, shapes):
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(slide_index, shape.shapes)
        else:
            yield slide_index, shape


ALL_CHECKS = []  # populated by register() below


def register(fn):
    ALL_CHECKS.append(fn)
    return fn
```

`pptx_a11y/checks/alt_text.py`:
```python
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes, register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref

_VISUAL_TYPES = {MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.LINKED_PICTURE, MSO_SHAPE_TYPE.CHART}


def _alt(shape) -> str:
    try:
        return shape._element._nvXxPr.cNvPr.get("descr") or ""
    except Exception:  # noqa: BLE001
        return ""


def _is_decorative(shape) -> bool:
    # PowerPoint marks decorative images with a specific extension; treat a
    # title of "decorative" as decorative for our purposes (and skip).
    try:
        return (shape._element._nvXxPr.cNvPr.get("title") or "").strip().lower() == "decorative"
    except Exception:  # noqa: BLE001
        return False


@register
def check(prs) -> list[Finding]:
    findings = []
    for slide_index, shape in iter_shapes(prs):
        if shape.shape_type not in _VISUAL_TYPES:
            continue
        if _is_decorative(shape):
            continue
        if not _alt(shape).strip():
            findings.append(
                Finding(
                    check_id="alt_text",
                    severity=Severity.ERROR,
                    slide_index=slide_index,
                    shape_ref=shape_ref(slide_index, shape),
                    message="Image is missing alternative text.",
                    suggestion="Add a short description of the image's content/purpose.",
                )
            )
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/checks/test_alt_text.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/checks tests/checks
git commit -m "feat: alt-text check and shape iterator"
```

---

### Task 4: Slide-title and metadata checks

**Files:**
- Create: `pptx_a11y/checks/slide_titles.py`, `pptx_a11y/checks/metadata.py`
- Test: `tests/checks/test_slide_titles.py`, `tests/checks/test_metadata.py`

**Interfaces:**
- Consumes: `Finding`, `Severity`, `register`.
- Produces: `slide_titles.check(prs) -> list[Finding]` (`check_id="slide_title"`, one per slide with an empty/absent title); `metadata.check(prs) -> list[Finding]` (`check_id="metadata"`, flags missing core title and/or missing language).

- [ ] **Step 1: Write the failing tests**

`tests/checks/test_slide_titles.py`:
```python
from pptx import Presentation
from pptx_a11y.checks.slide_titles import check
from tests.fixtures.build import clean_deck, deck_with_issues


def test_flags_slide_without_title(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.slide_index == 0 and f.check_id == "slide_title" for f in findings)


def test_clean_deck_titles_ok(tmp_path):
    prs = Presentation(clean_deck(str(tmp_path / "ok.pptx")))
    assert check(prs) == []
```

`tests/checks/test_metadata.py`:
```python
from pptx import Presentation
from pptx_a11y.checks.metadata import check


def test_flags_missing_core_title(tmp_path):
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    p = str(tmp_path / "m.pptx")
    prs.save(p)
    findings = check(Presentation(p))
    assert any("title" in f.message.lower() for f in findings)


def test_title_present_not_flagged_for_title(tmp_path):
    prs = Presentation()
    prs.core_properties.title = "Has Title"
    prs.slides.add_slide(prs.slide_layouts[6])
    p = str(tmp_path / "m.pptx")
    prs.save(p)
    findings = check(Presentation(p))
    assert not any("missing a document title" in f.message.lower() for f in findings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/checks/test_slide_titles.py tests/checks/test_metadata.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the checks**

`pptx_a11y/checks/slide_titles.py`:
```python
from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, slide in enumerate(prs.slides):
        title = slide.shapes.title
        text = (title.text if title is not None else "").strip()
        if not text:
            findings.append(
                Finding(
                    check_id="slide_title",
                    severity=Severity.ERROR,
                    slide_index=i,
                    message="Slide has no title.",
                    suggestion="Give every slide a unique, descriptive title.",
                )
            )
    return findings
```

`pptx_a11y/checks/metadata.py`:
```python
from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


@register
def check(prs) -> list[Finding]:
    findings = []
    if not (prs.core_properties.title or "").strip():
        findings.append(
            Finding(
                check_id="metadata",
                severity=Severity.WARNING,
                slide_index=0,
                message="Presentation is missing a document title.",
                suggestion="Set the document title in file properties.",
            )
        )
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/checks/test_slide_titles.py tests/checks/test_metadata.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/checks/slide_titles.py pptx_a11y/checks/metadata.py tests/checks/test_slide_titles.py tests/checks/test_metadata.py
git commit -m "feat: slide-title and metadata checks"
```

---

### Task 5: Contrast math utility

**Files:**
- Create: `pptx_a11y/color.py`
- Test: `tests/test_color.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `relative_luminance(rgb: tuple[int,int,int]) -> float`; `contrast_ratio(fg, bg) -> float`; `suggest_compliant_color(fg, bg, target: float) -> tuple[int,int,int]` (darkens/lightens fg toward black/white until `target` met, returns best effort).

- [ ] **Step 1: Write the failing test**

`tests/test_color.py`:
```python
import math
from pptx_a11y.color import relative_luminance, contrast_ratio, suggest_compliant_color


def test_black_on_white_is_21():
    assert math.isclose(contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, rel_tol=1e-3)


def test_same_color_is_1():
    assert math.isclose(contrast_ratio((120, 120, 120), (120, 120, 120)), 1.0, rel_tol=1e-3)


def test_luminance_white_is_1():
    assert math.isclose(relative_luminance((255, 255, 255)), 1.0, rel_tol=1e-3)


def test_suggestion_meets_target_against_white():
    fg = suggest_compliant_color((150, 150, 150), (255, 255, 255), target=4.5)
    assert contrast_ratio(fg, (255, 255, 255)) >= 4.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_color.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the color math**

`pptx_a11y/color.py`:
```python
def _channel(c: int) -> float:
    s = c / 255.0
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def suggest_compliant_color(fg, bg, target: float) -> tuple[int, int, int]:
    """Move fg toward black or white (whichever helps) until target is met."""
    toward = (0, 0, 0) if relative_luminance(bg) > 0.5 else (255, 255, 255)
    best = fg
    for step in range(1, 21):
        t = step / 20.0
        cand = tuple(round(fg[i] + (toward[i] - fg[i]) * t) for i in range(3))
        if contrast_ratio(cand, bg) >= target:
            return cand
        best = cand
    return best
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_color.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/color.py tests/test_color.py
git commit -m "feat: WCAG contrast math utility"
```

---

### Task 6: Contrast and font-size checks

**Files:**
- Create: `pptx_a11y/checks/contrast.py`, `pptx_a11y/checks/font_size.py`, `pptx_a11y/textutil.py`
- Test: `tests/checks/test_contrast.py`, `tests/checks/test_font_size.py`

**Interfaces:**
- Consumes: `color.contrast_ratio`, `color.suggest_compliant_color`, `Finding`, `register`.
- Produces: `textutil.iter_runs(prs) -> Iterator[(slide_index, shape, paragraph, run)]`; `textutil.run_rgb(run) -> tuple|None`; `textutil.run_pt(run) -> float|None`; `contrast.check`, `font_size.check`. Contrast emits `check_id="contrast"` with the measured ratio and a `suggestion` color when both fg+bg are resolvable, else an `INFO` "indeterminate" finding. Font size emits `check_id="font_size"` for runs under 18pt.

- [ ] **Step 1: Write the failing tests**

`tests/checks/test_font_size.py`:
```python
from pptx import Presentation
from pptx_a11y.checks.font_size import check
from tests.fixtures.build import deck_with_issues


def test_flags_small_font(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.check_id == "font_size" and f.slide_index == 1 for f in findings)
```

`tests/checks/test_contrast.py`:
```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx_a11y.checks.contrast import check


def _deck_low_contrast(path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tf = s.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame
    run = tf.paragraphs[0].add_run()
    run.text = "low contrast"
    run.font.size = Pt(24)
    run.font.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)  # light grey on default white
    prs.save(path)
    return path


def test_flags_low_contrast_with_ratio_and_suggestion(tmp_path):
    prs = Presentation(_deck_low_contrast(str(tmp_path / "c.pptx")))
    findings = check(prs)
    hits = [f for f in findings if f.check_id == "contrast"]
    assert hits
    assert "ratio" in hits[0].message.lower()
    assert hits[0].suggestion is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/checks/test_contrast.py tests/checks/test_font_size.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement text utilities and checks**

`pptx_a11y/textutil.py`:
```python
from pptx.util import Pt


def iter_runs(prs):
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    yield i, shape, para, run


def run_rgb(run):
    try:
        color = run.font.color
        if color and color.type is not None and color.rgb is not None:
            rgb = color.rgb
            return (rgb[0], rgb[1], rgb[2])
    except Exception:  # noqa: BLE001 - theme/inherited colors are unresolvable here
        return None
    return None


def run_pt(run) -> float | None:
    sz = run.font.size
    return sz.pt if sz is not None else None
```

`pptx_a11y/checks/font_size.py`:
```python
from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref
from pptx_a11y.textutil import iter_runs, run_pt

MIN_PT = 18.0


@register
def check(prs) -> list[Finding]:
    findings = []
    seen = set()
    for i, shape, _para, run in iter_runs(prs):
        pt = run_pt(run)
        if pt is not None and pt < MIN_PT and not run.text.strip() == "":
            key = (i, shape.shape_id)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    check_id="font_size",
                    severity=Severity.WARNING,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Text is {pt:.0f}pt, below the {MIN_PT:.0f}pt minimum.",
                    suggestion=f"Increase body text to at least {MIN_PT:.0f}pt.",
                )
            )
    return findings
```

`pptx_a11y/checks/contrast.py`:
```python
from pptx_a11y.checks import register
from pptx_a11y.color import contrast_ratio, suggest_compliant_color
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref
from pptx_a11y.textutil import iter_runs, run_rgb, run_pt

DEFAULT_BG = (255, 255, 255)  # assume white slide background when unresolved


def _target(run) -> float:
    pt = run_pt(run) or 18.0
    bold = bool(run.font.bold)
    large = pt >= 18.0 or (pt >= 14.0 and bold)
    return 3.0 if large else 4.5


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, shape, _para, run in iter_runs(prs):
        if not run.text.strip():
            continue
        fg = run_rgb(run)
        if fg is None:
            findings.append(
                Finding(
                    check_id="contrast",
                    severity=Severity.INFO,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message="Text color is theme/inherited; contrast is indeterminate.",
                    suggestion="Verify this text meets 4.5:1 contrast manually.",
                )
            )
            continue
        target = _target(run)
        ratio = contrast_ratio(fg, DEFAULT_BG)
        if ratio < target:
            sug = suggest_compliant_color(fg, DEFAULT_BG, target)
            findings.append(
                Finding(
                    check_id="contrast",
                    severity=Severity.ERROR,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Contrast ratio {ratio:.1f}:1 is below {target:.1f}:1 (assuming white background).",
                    suggestion=f"Use color #{sug[0]:02X}{sug[1]:02X}{sug[2]:02X} or darker.",
                )
            )
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/checks/test_contrast.py tests/checks/test_font_size.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/textutil.py pptx_a11y/checks/contrast.py pptx_a11y/checks/font_size.py tests/checks/test_contrast.py tests/checks/test_font_size.py
git commit -m "feat: contrast and font-size checks"
```

---

### Task 7: Link-text, table, reading-order, media checks

**Files:**
- Create: `pptx_a11y/checks/link_text.py`, `pptx_a11y/checks/tables.py`, `pptx_a11y/checks/reading_order.py`, `pptx_a11y/checks/media_captions.py`
- Test: `tests/checks/test_link_text.py`, `tests/checks/test_tables.py`

**Interfaces:**
- Consumes: `iter_runs`, `iter_shapes`, `Finding`, `register`.
- Produces: four `check(prs) -> list[Finding]` functions with `check_id` values `link_text`, `table`, `reading_order`, `media`. (Reading-order and media are conservative detectors; tested via the pipeline aggregate in Task 11, so only link_text and tables get dedicated tests here.)

- [ ] **Step 1: Write the failing tests**

`tests/checks/test_link_text.py`:
```python
from pptx import Presentation
from pptx_a11y.checks.link_text import check
from tests.fixtures.build import deck_with_issues


def test_flags_click_here(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.check_id == "link_text" for f in findings)
```

`tests/checks/test_tables.py`:
```python
from pptx import Presentation
from pptx.util import Inches
from pptx_a11y.checks.tables import check


def _deck_with_table(path, header):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    gf = s.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(2))
    tbl = gf.table
    tbl.first_row = header
    prs.save(path)
    return path


def test_flags_table_without_header_row(tmp_path):
    prs = Presentation(_deck_with_table(str(tmp_path / "t.pptx"), header=False))
    findings = check(prs)
    assert any(f.check_id == "table" for f in findings)


def test_table_with_header_row_ok(tmp_path):
    prs = Presentation(_deck_with_table(str(tmp_path / "t.pptx"), header=True))
    findings = check(prs)
    assert not any("header" in f.message.lower() for f in findings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/checks/test_link_text.py tests/checks/test_tables.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the checks**

`pptx_a11y/checks/link_text.py`:
```python
from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref
from pptx_a11y.textutil import iter_runs

_BAD = {"click here", "here", "link", "read more", "more", "this"}


def _looks_like_url(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("http://") or t.startswith("https://") or t.startswith("www.")


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, shape, _para, run in iter_runs(prs):
        if run.hyperlink is None or not run.hyperlink.address:
            continue
        text = run.text.strip()
        if text.lower() in _BAD or _looks_like_url(text) or not text:
            findings.append(
                Finding(
                    check_id="link_text",
                    severity=Severity.WARNING,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Link text {text!r} is not descriptive.",
                    suggestion="Use link text that describes the destination.",
                )
            )
    return findings
```

`pptx_a11y/checks/tables.py`:
```python
from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if not shape.has_table:
                continue
            tbl = shape.table
            if not tbl.first_row:
                findings.append(
                    Finding(
                        check_id="table",
                        severity=Severity.ERROR,
                        slide_index=i,
                        shape_ref=shape_ref(i, shape),
                        message="Table has no header row.",
                        suggestion="Mark the first row as a header row.",
                    )
                )
            # merged-cell detection: a spanned cell reports span_height/width > 1
            for row in tbl.rows:
                for cell in row.cells:
                    if cell.is_merge_origin and (cell.span_height > 1 or cell.span_width > 1):
                        findings.append(
                            Finding(
                                check_id="table",
                                severity=Severity.WARNING,
                                slide_index=i,
                                shape_ref=shape_ref(i, shape),
                                message="Table contains merged cells.",
                                suggestion="Avoid merged cells; use a simple grid.",
                            )
                        )
                        break
                else:
                    continue
                break
    return findings
```

`pptx_a11y/checks/reading_order.py`:
```python
from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


@register
def check(prs) -> list[Finding]:
    """Conservative: flag slides with many shapes where no title comes first,
    a common screen-reader reading-order problem."""
    findings = []
    for i, slide in enumerate(prs.slides):
        shapes = list(slide.shapes)
        if len(shapes) <= 1:
            continue
        title = slide.shapes.title
        if title is not None and shapes[0] is not title:
            findings.append(
                Finding(
                    check_id="reading_order",
                    severity=Severity.INFO,
                    slide_index=i,
                    message="Slide title is not first in the reading order.",
                    suggestion="Check the selection pane so the title is read first.",
                )
            )
    return findings
```

`pptx_a11y/checks/media_captions.py`:
```python
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes, register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref


@register
def check(prs) -> list[Finding]:
    findings = []
    for slide_index, shape in iter_shapes(prs):
        if shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
            findings.append(
                Finding(
                    check_id="media",
                    severity=Severity.WARNING,
                    slide_index=slide_index,
                    shape_ref=shape_ref(slide_index, shape),
                    message="Embedded media may lack captions.",
                    suggestion="Provide captions/transcript for audio and video.",
                )
            )
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/checks/test_link_text.py tests/checks/test_tables.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Ensure all checks are registered**

Add explicit imports so `ALL_CHECKS` is populated when `pptx_a11y.checks` is imported. Append to `pptx_a11y/checks/__init__.py`:
```python
def load_all():
    """Import every check module so each @register call runs. Idempotent."""
    from importlib import import_module
    for name in (
        "alt_text", "slide_titles", "metadata", "contrast",
        "font_size", "link_text", "tables", "reading_order", "media_captions",
    ):
        import_module(f"{__name__}.{name}")
    return ALL_CHECKS
```

- [ ] **Step 6: Commit**

```bash
git add pptx_a11y/checks tests/checks/test_link_text.py tests/checks/test_tables.py
git commit -m "feat: link-text, table, reading-order, media checks + registry loader"
```

---

### Task 8: Describer protocol + Claude vision implementation

**Files:**
- Create: `pptx_a11y/alt_text_ai.py`
- Test: `tests/test_alt_text_ai.py`

**Interfaces:**
- Consumes: `anthropic` SDK.
- Produces: `Describer` Protocol with `describe(image_bytes: bytes, media_type: str, context: str) -> str | None`; `NullDescriber` (always returns `None`); `ClaudeDescriber(api_key)` calling `claude-sonnet-4-6`, returning a one-sentence description or `None` on any API error.

- [ ] **Step 1: Write the failing test**

`tests/test_alt_text_ai.py`:
```python
from pptx_a11y.alt_text_ai import NullDescriber, ClaudeDescriber


def test_null_describer_returns_none():
    assert NullDescriber().describe(b"x", "image/png", "ctx") is None


def test_claude_describer_returns_text(monkeypatch):
    class _FakeMessages:
        def create(self, **kwargs):
            class R:
                content = [type("B", (), {"text": "A red square."})()]
            return R()

    class _FakeClient:
        def __init__(self, **kwargs):
            self.messages = _FakeMessages()

    import pptx_a11y.alt_text_ai as mod
    monkeypatch.setattr(mod, "Anthropic", _FakeClient)
    d = ClaudeDescriber(api_key="test")
    assert d.describe(b"\x89PNG", "image/png", "slide 1") == "A red square."


def test_claude_describer_handles_api_error(monkeypatch):
    class _Boom:
        def __init__(self, **kwargs):
            raise RuntimeError("no network")

    import pptx_a11y.alt_text_ai as mod
    monkeypatch.setattr(mod, "Anthropic", _Boom)
    d = ClaudeDescriber(api_key="test")
    assert d.describe(b"x", "image/png", "ctx") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_alt_text_ai.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the describers**

`pptx_a11y/alt_text_ai.py`:
```python
import base64
from typing import Protocol

from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"
_PROMPT = (
    "Write concise alternative text (one sentence, under 125 characters) describing "
    "this image for a screen-reader user. Describe content and purpose; do not start "
    "with 'image of'. Context: {context}"
)


class Describer(Protocol):
    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None: ...


class NullDescriber:
    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None:
        return None


class ClaudeDescriber:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None:
        try:
            client = Anthropic(api_key=self._api_key)
            b64 = base64.standard_b64encode(image_bytes).decode("ascii")
            resp = client.messages.create(
                model=MODEL,
                max_tokens=120,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                            {"type": "text", "text": _PROMPT.format(context=context)},
                        ],
                    }
                ],
            )
            text = resp.content[0].text.strip()
            return text or None
        except Exception:  # noqa: BLE001 - any failure degrades to flag-only
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_alt_text_ai.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/alt_text_ai.py tests/test_alt_text_ai.py
git commit -m "feat: Describer protocol and Claude vision implementation"
```

---

### Task 9: Fixers (alt text, titles, metadata)

**Files:**
- Create: `pptx_a11y/fixers/__init__.py`, `pptx_a11y/fixers/alt_text.py`, `pptx_a11y/fixers/slide_titles.py`, `pptx_a11y/fixers/metadata.py`, `pptx_a11y/imageutil.py`
- Test: `tests/fixers/__init__.py`, `tests/fixers/test_alt_text_fixer.py`, `tests/fixers/test_titles_metadata_fixers.py`

**Interfaces:**
- Consumes: `Describer`, `iter_shapes`, `Change`.
- Produces: `imageutil.image_bytes_and_type(picture) -> (bytes, str)|None`; three fixers each `fix(prs, describer: Describer) -> list[Change]` with `fixer_id` in `{alt_text, slide_title, metadata}`; `fixers/__init__.py` exposes `ALL_FIXERS` + `load_all()`. Alt-text fixer embeds AI text via `cNvPr.set("descr", ...)` and sets `machine_generated=True`; when the describer returns `None` it makes no change (leaving the existing alt-text ERROR finding to stand).

- [ ] **Step 1: Write the failing tests**

`tests/fixers/test_alt_text_fixer.py`:
```python
from pptx import Presentation
from pptx_a11y.fixers.alt_text import fix
from tests.fixtures.build import deck_with_issues


class _StubDescriber:
    def describe(self, image_bytes, media_type, context):
        return "A solid red square."


class _NullDescriber:
    def describe(self, image_bytes, media_type, context):
        return None


def _first_picture(prs):
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                return shape
    return None


def test_alt_text_fix_embeds_description(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    changes = fix(prs, _StubDescriber())
    assert any(c.fixer_id == "alt_text" and c.machine_generated for c in changes)
    pic = _first_picture(prs)
    assert pic._element._nvXxPr.cNvPr.get("descr") == "A solid red square."


def test_alt_text_fix_no_change_when_describer_returns_none(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    changes = fix(prs, _NullDescriber())
    assert changes == []
    pic = _first_picture(prs)
    assert not (pic._element._nvXxPr.cNvPr.get("descr") or "")
```

`tests/fixers/test_titles_metadata_fixers.py`:
```python
from pptx import Presentation
from pptx_a11y.fixers.slide_titles import fix as fix_titles
from pptx_a11y.fixers.metadata import fix as fix_metadata
from tests.fixtures.build import deck_with_issues


class _TitleDescriber:
    def describe(self, image_bytes, media_type, context):
        return "Overview"


def test_title_fixer_fills_empty_title(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    changes = fix_titles(prs, _TitleDescriber())
    assert any(c.fixer_id == "slide_title" and c.machine_generated for c in changes)
    assert prs.slides[0].shapes.title.text.strip() != ""


def test_metadata_fixer_sets_title(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    prs.core_properties.title = ""
    changes = fix_metadata(prs, _TitleDescriber())
    assert any(c.fixer_id == "metadata" for c in changes)
    assert prs.core_properties.title.strip() != ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/fixers -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement image util, registry, and fixers**

`pptx_a11y/imageutil.py`:
```python
def image_bytes_and_type(picture):
    """Return (bytes, media_type) for a Picture shape, or None if unavailable."""
    try:
        img = picture.image
        return img.blob, img.content_type
    except Exception:  # noqa: BLE001
        return None
```

`pptx_a11y/fixers/__init__.py`:
```python
ALL_FIXERS = []


def register(fn):
    ALL_FIXERS.append(fn)
    return fn


def load_all():
    from importlib import import_module
    for name in ("alt_text", "slide_titles", "metadata"):
        import_module(f"{__name__}.{name}")
    return ALL_FIXERS
```

`pptx_a11y/fixers/alt_text.py`:
```python
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes
from pptx_a11y.fixers import register
from pptx_a11y.imageutil import image_bytes_and_type
from pptx_a11y.models import Change
from pptx_a11y.refs import shape_ref


def _alt(shape) -> str:
    try:
        return shape._element._nvXxPr.cNvPr.get("descr") or ""
    except Exception:  # noqa: BLE001
        return ""


@register
def fix(prs, describer) -> list[Change]:
    changes = []
    for slide_index, shape in iter_shapes(prs):
        if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
            continue
        if _alt(shape).strip():
            continue
        payload = image_bytes_and_type(shape)
        if payload is None:
            continue
        blob, media_type = payload
        desc = describer.describe(blob, media_type, f"slide {slide_index + 1}")
        if not desc:
            continue
        shape._element._nvXxPr.cNvPr.set("descr", desc)
        changes.append(
            Change(
                fixer_id="alt_text",
                slide_index=slide_index,
                shape_ref=shape_ref(slide_index, shape),
                description=f'Added alt text: "{desc}"',
                machine_generated=True,
            )
        )
    return changes
```

`pptx_a11y/fixers/slide_titles.py`:
```python
from pptx_a11y.fixers import register
from pptx_a11y.models import Change


def _slide_text(slide) -> str:
    parts = []
    for shape in slide.shapes:
        if shape.has_text_frame and shape.text_frame.text.strip():
            parts.append(shape.text_frame.text.strip())
    return " ".join(parts)[:500]


@register
def fix(prs, describer) -> list[Change]:
    changes = []
    for i, slide in enumerate(prs.slides):
        title = slide.shapes.title
        if title is None:
            continue  # no title placeholder to fill; left as a finding
        if title.text.strip():
            continue
        context = _slide_text(slide) or f"slide {i + 1}"
        suggestion = describer.describe(b"", "text/plain", f"Suggest a 3-6 word slide title. Slide text: {context}")
        new_title = (suggestion or f"Slide {i + 1}").strip()
        title.text = new_title
        changes.append(
            Change(
                fixer_id="slide_title",
                slide_index=i,
                description=f'Added slide title: "{new_title}"',
                machine_generated=True,
            )
        )
    return changes
```

Note: the title describer is the same `Describer`; `ClaudeDescriber.describe` with empty image bytes still returns text because the prompt carries the slide text. (If a real image is required by the model, an empty-bytes call returns `None` and we fall back to `"Slide N"`.)

`pptx_a11y/fixers/metadata.py`:
```python
from pptx_a11y.fixers import register
from pptx_a11y.models import Change


@register
def fix(prs, describer) -> list[Change]:
    changes = []
    if not (prs.core_properties.title or "").strip():
        first_title = ""
        if len(prs.slides) and prs.slides[0].shapes.title is not None:
            first_title = prs.slides[0].shapes.title.text.strip()
        new = first_title or "Presentation"
        prs.core_properties.title = new
        changes.append(
            Change(
                fixer_id="metadata",
                slide_index=0,
                description=f'Set document title to "{new}".',
                machine_generated=False,
            )
        )
    return changes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/fixers -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/fixers pptx_a11y/imageutil.py tests/fixers
git commit -m "feat: alt-text, title, and metadata fixers"
```

---

### Task 10: Report generation (JSON + HTML)

**Files:**
- Create: `pptx_a11y/report/__init__.py`, `pptx_a11y/report/json_report.py`, `pptx_a11y/report/html_report.py`
- Test: `tests/report/__init__.py`, `tests/report/test_reports.py`

**Interfaces:**
- Consumes: `FileResult`, `Finding`, `Change`, `Severity`.
- Produces: `json_report.render(result: FileResult) -> str`; `html_report.render(result: FileResult) -> str` (self-contained HTML, inline CSS, grouped by slide, severity-colored, machine-generated changes marked "review this", summary header with counts).

- [ ] **Step 1: Write the failing test**

`tests/report/test_reports.py`:
```python
import json
from pptx_a11y.models import FileResult, Finding, Change, Severity
from pptx_a11y.report import json_report, html_report


def _result():
    return FileResult(
        source_path="deck.pptx",
        output_path="deck_accessible.pptx",
        findings=[
            Finding(check_id="alt_text", severity=Severity.ERROR, slide_index=0,
                    message="missing alt", shape_ref="slide0:shape5", auto_fixed=True),
            Finding(check_id="contrast", severity=Severity.WARNING, slide_index=1,
                    message="low contrast", suggestion="use #333333"),
        ],
        changes=[
            Change(fixer_id="alt_text", slide_index=0, description="Added alt text",
                   machine_generated=True),
        ],
    )


def test_json_report_roundtrips():
    data = json.loads(json_report.render(_result()))
    assert data["source_path"] == "deck.pptx"
    assert data["summary"]["error"] == 1
    assert len(data["findings"]) == 2
    assert data["changes"][0]["machine_generated"] is True


def test_html_report_contains_key_content():
    html = html_report.render(_result())
    assert "<html" in html.lower()
    assert "deck.pptx" in html
    assert "review this" in html.lower()       # machine-generated marker
    assert "low contrast" in html
    assert "use #333333" in html


def test_html_escapes_user_text():
    r = _result()
    r.findings[0].message = "bad <script>alert(1)</script>"
    html = html_report.render(r)
    assert "<script>alert(1)</script>" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/report/test_reports.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the reports**

`pptx_a11y/report/__init__.py`:
```python
from pptx_a11y.models import FileResult, Severity


def summary_counts(result: FileResult) -> dict:
    counts = {s.value: 0 for s in Severity}
    for f in result.findings:
        counts[f.severity.value] += 1
    counts["auto_fixed"] = sum(1 for f in result.findings if f.auto_fixed)
    counts["changes"] = len(result.changes)
    return counts
```

`pptx_a11y/report/json_report.py`:
```python
import json
from dataclasses import asdict
from pptx_a11y.models import FileResult
from pptx_a11y.report import summary_counts


def render(result: FileResult) -> str:
    payload = {
        "source_path": result.source_path,
        "output_path": result.output_path,
        "error": result.error,
        "summary": summary_counts(result),
        "findings": [
            {**asdict(f), "severity": f.severity.value} for f in result.findings
        ],
        "changes": [asdict(c) for c in result.changes],
    }
    return json.dumps(payload, indent=2)
```

`pptx_a11y/report/html_report.py`:
```python
from html import escape
from pptx_a11y.models import FileResult
from pptx_a11y.report import summary_counts

_CSS = """
body{font-family:system-ui,Arial,sans-serif;margin:2rem;color:#1a1a1a}
h1{font-size:1.4rem} .sum{display:flex;gap:1rem;margin:1rem 0}
.pill{padding:.3rem .7rem;border-radius:1rem;font-size:.85rem}
.error{background:#fdecea;color:#a3140b} .warning{background:#fff4e5;color:#8a5300}
.info{background:#e8f0fe;color:#174ea6} .ok{background:#e6f4ea;color:#137333}
.slide{border:1px solid #e0e0e0;border-radius:8px;margin:1rem 0;padding:1rem}
.item{padding:.5rem 0;border-bottom:1px solid #f0f0f0}
.tag{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;margin-right:.5rem}
.review{background:#fff4e5;color:#8a5300;padding:.1rem .4rem;border-radius:4px;font-size:.75rem}
.sug{color:#444;font-size:.9rem}
"""


def _by_slide(items):
    out: dict[int, list] = {}
    for it in items:
        out.setdefault(it.slide_index, []).append(it)
    return dict(sorted(out.items()))


def render(result: FileResult) -> str:
    s = summary_counts(result)
    rows = []
    rows.append(f"<h1>Accessibility report — {escape(result.source_path)}</h1>")
    if result.error:
        rows.append(f'<p class="pill error">Could not process: {escape(result.error)}</p>')
        return _doc("".join(rows))
    if result.output_path:
        rows.append(f"<p>Corrected file: <code>{escape(result.output_path)}</code></p>")
    rows.append(
        '<div class="sum">'
        f'<span class="pill error">{s["error"]} errors</span>'
        f'<span class="pill warning">{s["warning"]} warnings</span>'
        f'<span class="pill info">{s["info"]} info</span>'
        f'<span class="pill ok">{s["auto_fixed"]} auto-fixed</span>'
        "</div>"
    )

    findings_by_slide = _by_slide(result.findings)
    changes_by_slide = _by_slide(result.changes)
    all_slides = sorted(set(findings_by_slide) | set(changes_by_slide))
    for idx in all_slides:
        rows.append(f'<div class="slide"><h2>Slide {idx + 1}</h2>')
        for f in findings_by_slide.get(idx, []):
            fixed = ' <span class="review">auto-fixed</span>' if f.auto_fixed else ""
            sug = f'<div class="sug">Suggestion: {escape(f.suggestion)}</div>' if f.suggestion else ""
            rows.append(
                f'<div class="item"><span class="tag {f.severity.value}">{f.severity.value}</span>'
                f'{escape(f.message)}{fixed}{sug}</div>'
            )
        for c in changes_by_slide.get(idx, []):
            mark = ' <span class="review">review this</span>' if c.machine_generated else ""
            rows.append(f'<div class="item"><span class="tag ok">changed</span>{escape(c.description)}{mark}</div>')
        rows.append("</div>")
    return _doc("".join(rows))


def _doc(body: str) -> str:
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><style>{_CSS}</style></head><body>{body}</body></html>"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/report/test_reports.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/report tests/report
git commit -m "feat: JSON and HTML report generation"
```

---

### Task 11: Pipeline orchestration

**Files:**
- Create: `pptx_a11y/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `load_presentation`, `checks.load_all`, `fixers.load_all`, report renderers, `FileResult`, `Describer`.
- Produces: `process_file(path: str, describer: Describer, out_dir: str | None = None) -> FileResult` — runs checks, runs fixers, marks fixed findings, saves corrected copy with non-clobbering name, writes HTML+JSON reports next to it, returns the `FileResult`. `unique_path(path) -> str` helper.

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:
```python
import os
from pptx_a11y.pipeline import process_file, unique_path
from tests.fixtures.build import deck_with_issues, clean_deck


class _StubDescriber:
    def describe(self, image_bytes, media_type, context):
        return "A described image."


def test_process_file_produces_outputs_and_marks_fixed(tmp_path):
    src = deck_with_issues(str(tmp_path / "deck.pptx"))
    result = process_file(src, _StubDescriber())
    assert result.error is None
    assert os.path.exists(result.output_path)
    assert result.output_path.endswith("_accessible.pptx")
    assert os.path.exists(str(tmp_path / "deck_a11y_report.html"))
    assert os.path.exists(str(tmp_path / "deck_a11y_report.json"))
    # original untouched: still no alt text in the source file
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    src_prs = Presentation(src)
    pics = [sh for sl in src_prs.slides for sh in sl.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert not (pics[0]._element._nvXxPr.cNvPr.get("descr") or "")
    # an alt_text finding got marked auto_fixed
    assert any(f.check_id == "alt_text" and f.auto_fixed for f in result.findings)


def test_corrupt_file_returns_error_result(tmp_path):
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"nope")
    result = process_file(str(bad), _StubDescriber())
    assert result.error is not None
    assert result.output_path is None


def test_unique_path_disambiguates(tmp_path):
    p = tmp_path / "deck_accessible.pptx"
    p.write_bytes(b"x")
    assert unique_path(str(p)).endswith("deck_accessible_1.pptx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the pipeline**

`pptx_a11y/pipeline.py`:
```python
import os

from pptx_a11y.checks import load_all as load_checks
from pptx_a11y.fixers import load_all as load_fixers
from pptx_a11y.loader import LoadError, load_presentation
from pptx_a11y.models import FileResult
from pptx_a11y.report import html_report, json_report

# check_id <-> fixer_id pairs whose changes mean a finding was auto-fixed
_FIX_MAP = {"alt_text": "alt_text", "slide_title": "slide_title", "metadata": "metadata"}


def unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}_{n}{ext}"):
        n += 1
    return f"{base}_{n}{ext}"


def _mark_fixed(findings, changes):
    change_keys = {(c.fixer_id, c.slide_index, c.shape_ref) for c in changes}
    for f in findings:
        fixer = _FIX_MAP.get(f.check_id)
        if fixer and (fixer, f.slide_index, f.shape_ref) in change_keys:
            f.auto_fixed = True


def process_file(path: str, describer, out_dir: str | None = None) -> FileResult:
    out_dir = out_dir or os.path.dirname(os.path.abspath(path))
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        prs = load_presentation(path)
    except LoadError as exc:
        return FileResult(source_path=path, error=str(exc))

    findings = []
    for check in load_checks():
        findings.extend(check(prs))

    changes = []
    for fixer in load_fixers():
        changes.extend(fixer(prs, describer))

    _mark_fixed(findings, changes)

    out_path = unique_path(os.path.join(out_dir, f"{stem}_accessible.pptx"))
    prs.save(out_path)

    result = FileResult(source_path=path, output_path=out_path, findings=findings, changes=changes)

    with open(os.path.join(out_dir, f"{stem}_a11y_report.html"), "w", encoding="utf-8") as fh:
        fh.write(html_report.render(result))
    with open(os.path.join(out_dir, f"{stem}_a11y_report.json"), "w", encoding="utf-8") as fh:
        fh.write(json_report.render(result))
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add pptx_a11y/pipeline.py tests/test_pipeline.py
git commit -m "feat: end-to-end processing pipeline"
```

---

### Task 12: Settings (local API-key storage)

**Files:**
- Create: `pptx_a11y/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_settings(path: str | None = None) -> dict`; `save_api_key(key: str, path: str | None = None) -> None`; `get_describer(settings: dict) -> Describer` returning `ClaudeDescriber` when a key is present else `NullDescriber`. Default path: per-user app-data dir; tests pass an explicit path.

- [ ] **Step 1: Write the failing test**

`tests/test_settings.py`:
```python
from pptx_a11y.settings import load_settings, save_api_key, get_describer
from pptx_a11y.alt_text_ai import NullDescriber, ClaudeDescriber


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "settings.json")
    save_api_key("sk-test", p)
    assert load_settings(p)["api_key"] == "sk-test"


def test_missing_settings_returns_empty(tmp_path):
    assert load_settings(str(tmp_path / "none.json")) == {}


def test_get_describer_picks_implementation():
    assert isinstance(get_describer({}), NullDescriber)
    assert isinstance(get_describer({"api_key": "sk-x"}), ClaudeDescriber)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_settings.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement settings**

`pptx_a11y/settings.py`:
```python
import json
import os

from pptx_a11y.alt_text_ai import ClaudeDescriber, NullDescriber


def _default_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    return os.path.join(base, "SlideCheck", "settings.json")


def load_settings(path: str | None = None) -> dict:
    path = path or _default_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def save_api_key(key: str, path: str | None = None) -> None:
    path = path or _default_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = load_settings(path)
    data["api_key"] = key
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def get_describer(settings: dict):
    key = (settings.get("api_key") or "").strip()
    return ClaudeDescriber(key) if key else NullDescriber()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_settings.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/settings.py tests/test_settings.py
git commit -m "feat: local settings and API-key storage"
```

---

### Task 13: CLI (batch + folder summary)

**Files:**
- Create: `pptx_a11y/cli.py`; Modify: `pyproject.toml` (add `[project.scripts]` entry `slidecheck = "pptx_a11y.cli:main"`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `process_file`, `load_settings`, `get_describer`.
- Produces: `main(argv: list[str] | None = None) -> int`; processes a file or every `.pptx` in a folder (skipping `*_accessible.pptx` and temp `~$` files); prints a per-file summary line; returns exit code 0 unless a path is invalid.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
from pptx_a11y.cli import main
from tests.fixtures.build import deck_with_issues, clean_deck


def test_cli_processes_folder(tmp_path, monkeypatch, capsys):
    deck_with_issues(str(tmp_path / "a.pptx"))
    clean_deck(str(tmp_path / "b.pptx"))
    # force NullDescriber so no network is used
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    code = main([str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "a.pptx" in out and "b.pptx" in out
    assert (tmp_path / "a_accessible.pptx").exists()


def test_cli_bad_path_returns_nonzero():
    assert main(["/no/such/path.pptx"]) != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the CLI**

`pptx_a11y/cli.py`:
```python
import argparse
import os
import sys

from pptx_a11y.pipeline import process_file
from pptx_a11y.settings import get_describer, load_settings


def _pptx_in(folder: str) -> list[str]:
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".pptx"):
            continue
        if name.startswith("~$") or name.endswith("_accessible.pptx"):
            continue
        out.append(os.path.join(folder, name))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slidecheck", description="Check & fix PPTX accessibility.")
    parser.add_argument("path", help="A .pptx file or a folder of them.")
    args = parser.parse_args(argv)

    target = args.path
    if os.path.isdir(target):
        files = _pptx_in(target)
    elif os.path.isfile(target) and target.lower().endswith(".pptx"):
        files = [target]
    else:
        print(f"Not a .pptx file or folder: {target}", file=sys.stderr)
        return 2

    describer = get_describer(load_settings())
    for path in files:
        result = process_file(path, describer)
        if result.error:
            print(f"{os.path.basename(path)}: ERROR — {result.error}")
            continue
        s = {}
        for f in result.findings:
            s[f.severity.value] = s.get(f.severity.value, 0) + 1
        fixed = sum(1 for f in result.findings if f.auto_fixed)
        print(
            f"{os.path.basename(path)}: "
            f"{s.get('error', 0)} errors, {s.get('warning', 0)} warnings, "
            f"{fixed} auto-fixed -> {os.path.basename(result.output_path)}"
        )
    return 0
```

Add to `pyproject.toml` under `[project.scripts]`:
```toml
[project.scripts]
slidecheck = "pptx_a11y.cli:main"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/cli.py pyproject.toml tests/test_cli.py
git commit -m "feat: CLI for single-file and batch processing"
```

---

### Task 14: Drag-and-drop GUI

**Files:**
- Create: `pptx_a11y/gui.py`; Modify: `pyproject.toml` (`[project.scripts]` add `slidecheck-gui = "pptx_a11y.gui:main"`)
- Test: `tests/test_gui.py` (logic only — no window opened)

**Interfaces:**
- Consumes: `process_file`, `load_settings`, `save_api_key`, `get_describer`, `webbrowser`.
- Produces: `handle_drop(paths: list[str], describer, opener=webbrowser.open) -> list[FileResult]` (pure, testable: processes dropped files, opens each report); `main()` builds the Tkinter+tkinterdnd2 window and wires `handle_drop`. The window has a drop area and a "Set API key…" button. GUI construction is untested; `handle_drop` is fully tested.

- [ ] **Step 1: Write the failing test**

`tests/test_gui.py`:
```python
from pptx_a11y.gui import handle_drop
from tests.fixtures.build import deck_with_issues


class _StubDescriber:
    def describe(self, image_bytes, media_type, context):
        return "img"


def test_handle_drop_processes_and_opens_reports(tmp_path):
    a = deck_with_issues(str(tmp_path / "a.pptx"))
    opened = []
    results = handle_drop([a], _StubDescriber(), opener=opened.append)
    assert len(results) == 1
    assert results[0].output_path.endswith("_accessible.pptx")
    assert opened and opened[0].endswith("a_a11y_report.html")


def test_handle_drop_skips_non_pptx(tmp_path):
    txt = tmp_path / "note.txt"
    txt.write_text("hi")
    results = handle_drop([str(txt)], _StubDescriber(), opener=lambda *_: None)
    assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gui.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement GUI logic + window**

`pptx_a11y/gui.py`:
```python
import os
import webbrowser

from pptx_a11y.pipeline import process_file
from pptx_a11y.settings import get_describer, load_settings, save_api_key


def handle_drop(paths, describer, opener=webbrowser.open):
    results = []
    for path in paths:
        if not (os.path.isfile(path) and path.lower().endswith(".pptx")):
            continue
        if path.lower().endswith("_accessible.pptx"):
            continue
        result = process_file(path, describer)
        results.append(result)
        report = os.path.splitext(path)[0] + "_a11y_report.html"
        if os.path.exists(report):
            opener("file://" + os.path.abspath(report))
    return results


def _parse_drop(data: str) -> list[str]:
    """tkinterdnd2 delivers space-separated paths, brace-wrapped if they contain spaces."""
    import re
    return re.findall(r"\{[^}]*\}|\S+", data) and [p.strip("{}") for p in re.findall(r"\{[^}]*\}|\S+", data)]


def main():  # pragma: no cover - UI wiring
    from tkinterdnd2 import DND_FILES, TkinterDnD
    import tkinter as tk
    from tkinter import simpledialog, messagebox

    root = TkinterDnD.Tk()
    root.title("SlideCheck")
    root.geometry("460x300")

    info = tk.Label(root, text="Drop .pptx files here", width=50, height=8, relief="ridge", bg="#f5f5f5")
    info.pack(padx=20, pady=20, fill="both", expand=True)

    status = tk.Label(root, text="", fg="#137333")
    status.pack()

    def on_drop(event):
        paths = _parse_drop(event.data)
        describer = get_describer(load_settings())
        status.config(text="Processing…")
        root.update_idletasks()
        results = handle_drop(paths, describer)
        ok = sum(1 for r in results if not r.error)
        status.config(text=f"Done: {ok} file(s) processed. Reports opened in your browser.")

    info.drop_target_register(DND_FILES)
    info.dnd_bind("<<Drop>>", on_drop)

    def set_key():
        key = simpledialog.askstring("API key", "Enter your Anthropic API key (leave blank to skip AI alt text):", show="*")
        if key is not None:
            save_api_key(key.strip())
            messagebox.showinfo("SlideCheck", "API key saved.")

    tk.Button(root, text="Set API key…", command=set_key).pack(pady=10)
    root.mainloop()
```

Add to `pyproject.toml` `[project.scripts]`:
```toml
slidecheck-gui = "pptx_a11y.gui:main"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gui.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Manually smoke-test the window (optional, local)**

Run: `uv run slidecheck-gui`
Expected: a window opens with a drop area; dropping a `.pptx` produces outputs and opens the report. (Skip if running headless.)

- [ ] **Step 6: Commit**

```bash
git add pptx_a11y/gui.py pyproject.toml tests/test_gui.py
git commit -m "feat: drag-and-drop GUI"
```

---

### Task 15: Packaging docs + README

**Files:**
- Create: `packaging/build-windows.md`, `packaging/slidecheck.spec`, `README.md`

**Interfaces:**
- Consumes: nothing (documentation + PyInstaller spec).
- Produces: a documented path to a Windows `.exe` and end-user usage notes.

- [ ] **Step 1: Write the PyInstaller spec**

`packaging/slidecheck.spec`:
```python
# Run on Windows: uv run pyinstaller packaging/slidecheck.spec
# Produces dist/SlideCheck/SlideCheck.exe
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("tkinterdnd2", "pptx"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    ["../pptx_a11y/gui.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SlideCheck", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SlideCheck")
```

- [ ] **Step 2: Write the Windows build instructions**

`packaging/build-windows.md`:
```markdown
# Building the Windows app

A Windows `.exe` must be built on Windows (it cannot be cross-compiled from macOS).

## Option A — on a Windows machine
1. Install uv: https://docs.astral.sh/uv/
2. `git clone <repo>` and `cd slidecheck`
3. `uv sync`
4. `uv add --dev pyinstaller`
5. `uv run pyinstaller packaging/slidecheck.spec`
6. The app is in `dist/SlideCheck/`. Zip that folder; the user double-clicks `SlideCheck.exe`.

## Option B — GitHub Actions (no Windows machine needed)
Add `.github/workflows/build.yml` running on `windows-latest`: checkout, install uv,
`uv sync`, `uv add --dev pyinstaller`, `uv run pyinstaller packaging/slidecheck.spec`,
then upload `dist/SlideCheck/` as a build artifact.

## End-user notes
- First run: click **Set API key…** and paste an Anthropic API key to enable AI alt text.
  Without a key, the app still runs and flags missing alt text instead of writing it.
- Drop one or many `.pptx` files. For each, a `*_accessible.pptx` and a report are written
  next to the original; the report opens automatically.
```

- [ ] **Step 3: Write the README**

`README.md`:
```markdown
# SlideCheck

Scans PowerPoint (`.pptx`) files for WCAG 2.1 AA + Section 508 accessibility issues,
auto-fixes what is safe (alt text, slide titles, document metadata), and writes a clear
report. **Originals are never modified** — a `*_accessible.pptx` copy is produced.

## Use it
- **App:** double-click `SlideCheck.exe` (see `packaging/build-windows.md`), drop `.pptx` files.
- **Command line:** `uv run slidecheck path/to/file-or-folder`

## What it does
- **Auto-fixes:** missing image alt text (AI-generated), missing slide titles, document title.
- **Reports (manual fix):** color contrast, small fonts, tables without headers / merged cells,
  vague link text, reading-order issues, uncaptioned media.

## Develop
- `uv sync` then `uv run pytest`
```

- [ ] **Step 4: Run the full test suite once more**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add packaging README.md
git commit -m "docs: packaging instructions, PyInstaller spec, README"
```

---

## Self-Review

**Spec coverage:**
- Scan + report + auto-fix → Tasks 3–11 (checks, fixers, pipeline). ✓
- Drag-drop GUI (Windows) → Task 14 + packaging Task 15. ✓
- AI alt text (Claude vision), graceful degradation → Tasks 8, 9, 12 (NullDescriber path). ✓
- WCAG 2.1 AA + Section 508 checks (alt text, titles, contrast, font, tables, links, reading order, media, metadata) → Tasks 3, 4, 6, 7. ✓
- Apply-automatically + mark-for-review → fixers set `machine_generated`; HTML marks "review this" (Task 10). ✓
- Never overwrite originals / disambiguate → `unique_path` + corrected-copy output (Task 11). ✓
- Per-file isolation → `process_file` error path + CLI loop (Tasks 11, 13). ✓
- HTML + JSON + batch summary → Tasks 10, 13 (folder loop prints summary; per-file index deferred as noted below). ✓
- Local API-key storage → Task 12. ✓
- uv throughout → all run commands use `uv run`. ✓

**Deviations from spec (intentional, minor):**
- The spec mentioned a batch `index.html` linking each file's report. The plan prints a per-file
  summary to the console instead and defers the linked `index.html` to a future iteration (YAGNI
  for v0.1; the JSON reports already enable a roll-up). Flag for the user if they want it in v0.1.

**Placeholder scan:** none — every step contains real code/commands.

**Type consistency:** `Finding`/`Change`/`FileResult` fields used identically across Tasks 1–14;
`describe(image_bytes, media_type, context)` signature consistent across `alt_text_ai`, all fixers,
and every test stub; `check(prs)`/`fix(prs, describer)` signatures uniform across registries.
