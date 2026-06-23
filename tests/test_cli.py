from pptx_a11y.cli import main
from tests.fixtures.build import deck_with_issues, clean_deck


def test_cli_processes_folder(tmp_path, monkeypatch, capsys):
    deck_with_issues(str(tmp_path / "a.pptx"))
    clean_deck(str(tmp_path / "b.pptx"))
    # force NullDescriber so no network is used
    monkeypatch.setattr("pptx_a11y.cli.load_settings", lambda: {})
    code = main([str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "a.pptx" in out and "b.pptx" in out
    assert (tmp_path / "a_accessible.pptx").exists()


def test_cli_bad_path_returns_nonzero():
    assert main(["/no/such/path.pptx"]) != 0
