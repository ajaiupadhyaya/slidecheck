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
The repo already ships this as `.github/workflows/build-windows.yml` (runs on
`windows-latest`: checkout, install uv, `uv sync`, run the tests,
`uv run pyinstaller packaging/slidecheck.spec`, upload `dist/SlideCheck/`).

To get the app:
1. Push a version tag (`git tag v0.3.0 && git push origin v0.3.0`) or trigger the
   **Build Windows app** workflow manually from the repo's **Actions** tab.
2. Open the finished run, scroll to **Artifacts**, download `SlideCheck-windows`.
3. Unzip it and keep the whole `SlideCheck` folder together; the user double-clicks
   `SlideCheck.exe` inside it. (For a permanent, non-expiring link, attach the zip to a
   GitHub **Release** on the tag — artifacts expire after 90 days.)

## End-user notes
- First run: click **Set API key…** and paste an Anthropic API key to enable AI alt text.
  Without a key, the app still runs and flags missing alt text instead of writing it.
- Drop one or many `.pptx` files. For each, a `*_accessible.pptx` and a report are written
  next to the original; the report opens automatically.
