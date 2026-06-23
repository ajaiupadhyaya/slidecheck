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
