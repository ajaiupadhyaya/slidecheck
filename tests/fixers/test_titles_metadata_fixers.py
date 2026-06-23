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
