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
