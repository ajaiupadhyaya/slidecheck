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
