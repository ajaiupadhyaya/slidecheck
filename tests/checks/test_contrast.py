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
