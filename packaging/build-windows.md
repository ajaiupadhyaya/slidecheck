# Building the Windows app

A Windows `.exe` must be built on Windows (it cannot be cross-compiled from macOS).

## Option A — on a Windows machine
1. Install uv: https://docs.astral.sh/uv/
2. `git clone <repo>` and `cd slidecheck`
3. `uv sync`
4. `uv add --dev pyinstaller`
5. `uv run pyinstaller packaging/slidecheck.spec`
6. The app is in `dist/SlideCheck/`. Zip that folder; the user double-clicks `SlideCheck.exe`.

## Option B — GitHub Actions (no Windows machine needed)
Add `.github/workflows/build.yml` running on `windows-latest`: checkout, install uv,
`uv sync`, `uv add --dev pyinstaller`, `uv run pyinstaller packaging/slidecheck.spec`,
then upload `dist/SlideCheck/` as a build artifact.

## End-user notes
- First run: click **Set API key…** and paste an Anthropic API key to enable AI alt text.
  Without a key, the app still runs and flags missing alt text instead of writing it.
- Drop one or many `.pptx` files. For each, a `*_accessible.pptx` and a report are written
  next to the original; the report opens automatically.
