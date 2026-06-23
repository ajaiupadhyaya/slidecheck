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
