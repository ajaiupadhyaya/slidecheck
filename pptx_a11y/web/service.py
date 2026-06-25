"""Turn uploaded .pptx bytes into reports + fixed files, entirely inside a
TemporaryDirectory that is deleted before returning. Nothing is persisted.
"""
import os
import tempfile
from dataclasses import dataclass, field

from pptx_a11y.pipeline import process_file
from pptx_a11y.report import html_report, summary_counts


@dataclass
class FileOutput:
    filename: str
    error: str | None = None
    summary: dict = field(default_factory=dict)
    report_html: str | None = None
    fixed_filename: str | None = None
    fixed_bytes: bytes | None = None


@dataclass
class WebResult:
    files: list[FileOutput]


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0] or "upload"


def process_uploads(uploads: list[tuple[str, bytes]], describer) -> WebResult:
    """uploads: list of (original_filename, file_bytes). Returns one FileOutput
    per upload with rendered report HTML and fixed-file bytes."""
    outputs: list[FileOutput] = []
    with tempfile.TemporaryDirectory() as tmp:
        for filename, data in uploads:
            in_path = os.path.join(tmp, f"{_stem(filename)}.pptx")
            with open(in_path, "wb") as fh:
                fh.write(data)
            result = process_file(in_path, describer, out_dir=tmp)
            if result.error:
                outputs.append(FileOutput(filename=filename, error=result.error))
                continue
            with open(result.output_path, "rb") as fh:
                fixed_bytes = fh.read()
            outputs.append(
                FileOutput(
                    filename=filename,
                    summary=summary_counts(result),
                    report_html=html_report.render(result),
                    fixed_filename=os.path.basename(result.output_path),
                    fixed_bytes=fixed_bytes,
                )
            )
    return WebResult(files=outputs)
