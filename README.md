# SlideCheck

Scans PowerPoint (`.pptx`) files for WCAG 2.1 AA + Section 508 accessibility issues,
auto-fixes what is safe (alt text, slide titles, document metadata), and writes a clear
report. **Originals are never modified** — a `*_accessible.pptx` copy is produced.

## Use it
- **App:** download the `SlideCheck-windows` build, **unzip it, keep the whole `SlideCheck`
  folder together**, and double-click `SlideCheck.exe` inside it. Drop `.pptx` files on the
  window. (See `packaging/build-windows.md` for where to get the build.)
- **Command line:** `uv run slidecheck path/to/file-or-folder`

For a folder, each deck gets its own report **and** a single `index.html` summary linking them all.

## What it does
- **Auto-fixes:** missing image alt text (AI-generated), missing slide titles, document title
  and language.
- **Reports (manual fix):** color contrast, small fonts, tables without headers / merged cells,
  vague link text, reading-order issues, uncaptioned media.

## Known limitations

1. Charts and linked pictures are flagged for missing alt text but are not auto-described — only embedded raster images (PNG, JPEG, GIF, TIFF) receive AI-generated alt text.
2. EMF/WMF and other non-raster image formats cannot be auto-described and will always require a manual fix.
3. Color contrast resolves the real shape/slide/layout/master background; only when none of those is a solid color does it fall back to assuming white, and it says so in the message. Theme/inherited text colors are reported as "indeterminate" rather than guessed.
4. Font-size checks only see explicit run-level sizes; text whose size is inherited from a layout/master placeholder is not measured.
5. Uncaptioned-media detection flags every embedded audio/video as "may lack captions" — it cannot inspect for an actual caption track.

## Develop
- `uv sync` then `uv run pytest`
