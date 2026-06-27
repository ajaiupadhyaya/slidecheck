from pptx_a11y.models import Finding, Severity
from pptx_a11y.standards import score, coverage_matrix, SC_CATALOG


def _f(check, sev, scs, fixed=False):
    return Finding(check_id=check, severity=sev, slide_index=0, message="m",
                   sc_refs=scs, auto_fixed=fixed)


def test_score_perfect_when_no_open_findings():
    assert score([])["score"] == 100
    assert score([])["grade"] == "A"


def test_score_subtracts_by_severity_and_ignores_fixed():
    s = score([_f("a", Severity.ERROR, ["1.1.1"]), _f("b", Severity.WARNING, ["1.4.3"]),
               _f("c", Severity.ERROR, ["2.4.2"], fixed=True)])
    assert s["score"] == 100 - 8 - 3   # the fixed error is ignored
    assert s["errors"] == 1 and s["warnings"] == 1


def test_coverage_matrix_marks_fail_for_open_sc_and_na_for_interactive():
    rows = {r["sc"]: r for r in coverage_matrix([_f("a", Severity.ERROR, ["1.1.1"])])}
    assert rows["1.1.1"]["status"] == "FAIL"
    assert rows["2.4.2"]["status"] == "PASS"       # applicable, no open finding
    assert rows["2.5.8"]["status"] == "N_A"        # interactive-only
    assert rows["1.1.1"]["section508"] is True


def test_catalog_has_versions_and_levels():
    assert SC_CATALOG["1.4.3"]["version"] == "2.0" and SC_CATALOG["1.4.3"]["level"] == "AA"
    assert SC_CATALOG["1.4.11"]["version"] == "2.1"


# ---------------------------------------------------------------------------
# Honest classification of the former "structural PASS" SCs (no false PASS)
# ---------------------------------------------------------------------------

def test_identify_input_purpose_is_na_for_static_decks():
    # 1.3.5 applies to form-input autocomplete — never to static slides.
    rows = {r["sc"]: r for r in coverage_matrix([])}
    assert rows["1.3.5"]["status"] == "N_A"


def test_orientation_and_audio_control_are_needs_review_not_pass():
    # 1.3.4 (Orientation) and 1.4.2 (Audio Control) cannot be auto-verified,
    # so they must never silently report PASS.
    rows = {r["sc"]: r for r in coverage_matrix([])}
    assert rows["1.3.4"]["status"] == "NEEDS_REVIEW"
    assert rows["1.4.2"]["status"] == "NEEDS_REVIEW"


def test_language_of_parts_is_needs_review_not_false_pass():
    # 3.1.2 (Language of Parts) can't be auto-verified — detecting an *unmarked*
    # foreign passage needs language identification. A run carrying a differing
    # lang attribute is actually CORRECT markup, so we never auto-flag/"fix" it.
    # Honest treatment: surface for human review, never a silent PASS.
    rows = {r["sc"]: r for r in coverage_matrix([])}
    assert rows["3.1.2"]["status"] == "NEEDS_REVIEW"
