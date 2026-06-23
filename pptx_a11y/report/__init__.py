from pptx_a11y.models import FileResult, Severity


def summary_counts(result: FileResult) -> dict:
    counts = {s.value: 0 for s in Severity}
    for f in result.findings:
        counts[f.severity.value] += 1
    counts["auto_fixed"] = sum(1 for f in result.findings if f.auto_fixed)
    counts["changes"] = len(result.changes)
    return counts
