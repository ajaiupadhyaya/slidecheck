# SlideCheck

Scans PowerPoint (`.pptx`) files for WCAG 2.1 AA + Section 508 accessibility issues,
auto-fixes what is safe (alt text, slide titles, document metadata), and writes a clear
report. **Originals are never modified** — a `*_accessible.pptx` copy is produced.

## Use it
- **App:** double-click `SlideCheck.exe` (see `packaging/build-windows.md`), drop `.pptx` files.
- **Command line:** `uv run slidecheck path/to/file-or-folder`

## What it does
- **Auto-fixes:** missing image alt text (AI-generated), missing slide titles, document title.
- **Reports (manual fix):** color contrast, small fonts, tables without headers / merged cells,
  vague link text, reading-order issues, uncaptioned media.

## Develop
- `uv sync` then `uv run pytest`
