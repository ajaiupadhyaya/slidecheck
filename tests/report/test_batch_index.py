from pptx_a11y.models import Change, FileResult, Finding, Severity
from pptx_a11y.report import batch_index


def _results():
    return [
        FileResult(
            source_path="/decks/Lecture 1.pptx",
            output_path="/decks/Lecture 1_accessible.pptx",
            findings=[
                Finding("alt_text", Severity.ERROR, 0, "missing alt"),
                Finding("contrast", Severity.WARNING, 1, "low contrast"),
            ],
            changes=[Change("metadata", 0, "Set title", machine_generated=False)],
        ),
        FileResult(source_path="/decks/broken.pptx", error="Package not found"),
    ]


def test_render_lists_files_links_and_error_row():
    html = batch_index.render(_results())
    assert "Lecture 1.pptx" in html
    # link to the per-file report, URL-encoded (space -> %20)
    assert "Lecture%201_a11y_report.html" in html
    # the failed deck shows its error, not a broken link
    assert "broken.pptx" in html and "Package not found" in html
    assert "batch summary" in html.lower()


def test_render_escapes_filenames():
    r = [FileResult(source_path="/x/<script>.pptx", output_path="/x/o.pptx", findings=[])]
    html = batch_index.render(r)
    assert "<script>.pptx" not in html
    assert "&lt;script&gt;" in html


def test_write_index_writes_file(tmp_path):
    path = batch_index.write_index(_results(), str(tmp_path))
    assert path.endswith("index.html")
    assert (tmp_path / "index.html").exists()
    assert "Lecture 1.pptx" in (tmp_path / "index.html").read_text(encoding="utf-8")
