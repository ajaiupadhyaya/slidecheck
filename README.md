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

## Web app — interactive remediation studio (no install)

SlideCheck also runs as a web app: open the URL, enter the access password, and
drop a `.pptx`. Instead of a static report, you get an **interactive remediation
studio** — an accessibility **score + letter grade**, a **WCAG 2.1 AA / Section
508 coverage matrix**, and a **per-issue worklist**. Each issue explains itself
in plain language (with the offending image/text and its success criterion) and
offers an **AI-drafted fix you can Accept, edit, or Skip**; the score climbs as
you go. One click downloads a deck with **exactly the fixes you approved**, plus
a report. Files are processed in memory and **never stored**; the original is
never modified.

- **Architecture:** a stateless two-phase flow over the same `pptx_a11y` engine —
  `POST /api/analyze` returns findings + AI suggestions + score + coverage (it
  saves nothing); the browser builds a fix-plan from your choices; `POST
  /api/export` applies exactly that plan and returns the fixed deck. Served by a
  FastAPI app (`api/index.py`) with the static front end in `public/`, hosted as
  a long-running container on [Fly.io](https://fly.io) (no upload-size cap or
  request timeout, unlike serverless).
- **Configuration (Fly secrets):** `ANTHROPIC_API_KEY` (server-side Claude key
  for AI alt text) and `SLIDECHECK_PASSWORD` (the access password). Optional
  non-secret env in `fly.toml`: `SLIDECHECK_MAX_UPLOAD_MB` (default 40),
  `SLIDECHECK_MAX_AI_IMAGES` (default 40).
- **Local dev:** `SLIDECHECK_PASSWORD=dev uv run uvicorn api.index:app --reload`,
  then open http://localhost:8000.
- **Deploy:**
  ```bash
  fly launch --no-deploy          # first time: creates/links the app from fly.toml
  fly secrets set ANTHROPIC_API_KEY=sk-... SLIDECHECK_PASSWORD=your-password
  fly deploy
  ```

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
6. For text inside a grouped shape, contrast is measured against the slide/layout/master background, not the group's own fill.

## Develop
- `uv sync` then `uv run pytest`
