from pptx_a11y.cli import main
from tests.fixtures.build import deck_with_issues, clean_deck


def test_cli_processes_folder(tmp_path, monkeypatch, capsys):
    deck_with_issues(str(tmp_path / "a.pptx"))
    clean_deck(str(tmp_path / "b.pptx"))
    # force NullDescriber so no network is used
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    code = main([str(tmp_path)])
    # a.pptx has an unfixable open ERROR (missing alt, no AI) → exit 1
    assert code == 1
    out = capsys.readouterr().out
    assert "a.pptx" in out and "b.pptx" in out
    assert (tmp_path / "a_accessible.pptx").exists()
    # folder processing writes a batch summary linking each report
    assert (tmp_path / "index.html").exists()
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "a_a11y_report.html" in index and "b_a11y_report.html" in index


def test_cli_bad_path_returns_nonzero():
    assert main(["/no/such/path.pptx"]) != 0


def test_cli_exit_0_when_clean(tmp_path, monkeypatch):
    clean_deck(str(tmp_path / "ok.pptx"))
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    assert main([str(tmp_path / "ok.pptx")]) == 0


def test_cli_exit_1_when_open_errors(tmp_path, monkeypatch):
    deck_with_issues(str(tmp_path / "bad.pptx"))
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    assert main(["--no-ai", str(tmp_path / "bad.pptx")]) == 1


def test_cli_dry_run_writes_no_files(tmp_path, monkeypatch, capsys):
    deck_with_issues(str(tmp_path / "bad.pptx"))
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    code = main(["--dry-run", str(tmp_path / "bad.pptx")])
    # dry-run still reports an exit-1 audit verdict for a deck with errors
    assert code == 1
    # ...but writes NOTHING
    assert not (tmp_path / "bad_accessible.pptx").exists()
    assert not (tmp_path / "bad_a11y_report.html").exists()
    assert not (tmp_path / "bad_a11y_report.json").exists()
    out = capsys.readouterr().out
    assert "bad.pptx" in out


def test_cli_corrupt_file_exits_nonzero(tmp_path, monkeypatch):
    # A file that cannot be opened is a hard failure, not "all good" — it must
    # not exit 0 and silently pass CI.
    bad = tmp_path / "corrupt.pptx"
    bad.write_bytes(b"this is not a pptx")
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    assert main([str(bad)]) != 0
    # ...and the same in dry-run.
    assert main(["--dry-run", str(bad)]) != 0


def test_cli_no_ai_does_not_construct_describer(tmp_path, monkeypatch):
    deck_with_issues(str(tmp_path / "bad.pptx"))

    def _boom(_settings):
        raise AssertionError("get_describer must not be called with --no-ai")

    monkeypatch.setattr("pptx_a11y.cli.get_describer", _boom)
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    # should run fine using NullDescriber, never calling get_describer
    assert main(["--no-ai", "--dry-run", str(tmp_path / "bad.pptx")]) == 1
