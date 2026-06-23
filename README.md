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

## Known limitations (v0.1)

1. Charts and linked pictures are flagged for missing alt text but are not auto-described — only embedded raster images (PNG, JPEG, GIF, TIFF) receive AI-generated alt text.
2. EMF/WMF and other non-raster image formats cannot be auto-described and will always require a manual fix.
3. Color-contrast checks assume a white slide background; dark-themed decks may produce false contrast warnings. Theme and inherited colors are reported as "indeterminate" rather than guessed.

## Develop
- `uv sync` then `uv run pytest`
