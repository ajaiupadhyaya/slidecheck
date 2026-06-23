import json
from dataclasses import asdict
from pptx_a11y.models import FileResult
from pptx_a11y.report import summary_counts


def render(result: FileResult) -> str:
    payload = {
        "source_path": result.source_path,
        "output_path": result.output_path,
        "error": result.error,
        "summary": summary_counts(result),
        "findings": [
            {**asdict(f), "severity": f.severity.value} for f in result.findings
        ],
        "changes": [asdict(c) for c in result.changes],
    }
    return json.dumps(payload, indent=2)
