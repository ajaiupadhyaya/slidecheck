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
