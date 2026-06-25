from pptx import Presentation
from pptx_a11y.checks.font_size import check
from tests.fixtures.build import deck_with_issues


def test_flags_small_font(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.check_id == "font_size" and f.slide_index == 1 for f in findings)
    # metadata assertions
    hit = next(f for f in findings if f.check_id == "font_size")
    assert hit.fix_action == "bump_font_size"
    assert hit.fixable is True
    assert hit.current_value == "10"
    assert "shape_id" in hit.target and "para" in hit.target and "run" in hit.target
    assert hit.sc_refs == ["1.4.4"]
