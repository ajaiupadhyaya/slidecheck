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
