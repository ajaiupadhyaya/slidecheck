from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if not shape.has_table:
                continue
            tbl = shape.table
            if not tbl.first_row:
                findings.append(
                    Finding(
                        check_id="table",
                        severity=Severity.ERROR,
                        slide_index=i,
                        shape_ref=shape_ref(i, shape),
                        message="Table has no header row.",
                        suggestion="Mark the first row as a header row.",
                    )
                )
            # merged-cell detection: a spanned cell reports span_height/width > 1
            for row in tbl.rows:
                for cell in row.cells:
                    if cell.is_merge_origin and (cell.span_height > 1 or cell.span_width > 1):
                        findings.append(
                            Finding(
                                check_id="table",
                                severity=Severity.WARNING,
                                slide_index=i,
                                shape_ref=shape_ref(i, shape),
                                message="Table contains merged cells.",
                                suggestion="Avoid merged cells; use a simple grid.",
                            )
                        )
                        break
                else:
                    continue
                break
    return findings
