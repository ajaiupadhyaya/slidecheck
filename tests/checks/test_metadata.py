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
