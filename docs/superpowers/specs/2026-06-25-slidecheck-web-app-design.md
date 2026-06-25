# SlideCheck Web App — Design

**Date:** 2026-06-25
**Status:** Approved (design); pending spec review
**Author:** ajaiupadhyaya (with Claude Code)

## Problem

SlideCheck currently ships as a Windows `.exe` (Tkinter GUI) plus a CLI. The
intended user — a professor — uses a **state-issued Windows laptop that requires
an admin password to install any application**, which she does not have. A
downloadable app is therefore unusable to her.

She needs a **URL she can open in a browser** with **zero installation**: drop a
`.pptx`, get a fixed copy + an accessibility report back.

## Goals

- A browser-based front end requiring no install on the user's machine.
- Reuse the existing `pptx_a11y` engine verbatim — no rewrite of accessibility
  logic; the existing 72 engine tests remain valid.
- Auto-alt-text "just works" for the user — she never sees or supplies an API key.
- Private: usable by one person, gated by a single shared password; safe from
  random crawlers burning the AI key.
- Privacy-preserving: course materials are processed ephemerally and never
  persisted.

## Non-goals (YAGNI)

- User accounts, multi-tenant auth, or a user database.
- Public/abuse-hardened deployment (rate limiting beyond the password gate).
- Persisting uploads, history, or results.
- Rewriting or restructuring the accessibility engine.
- Changing the existing CLI or desktop GUI behavior.

## Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Access model | Private — one shared password | Just for the user's mother; keeps the AI key safe and cost controlled. |
| AI alt-text key | Server-side, owner-funded (`ANTHROPIC_API_KEY`) | User never handles keys; low volume ⇒ negligible cost. |
| Hosting | Vercel (static front end + Python serverless function) | Free, always-reachable (static page never sleeps), custom domain, GitHub auto-deploy, matches the owner's existing stack. |
| Codebase | Same `slidecheck` repo, new `api/` + `public/` | One engine, two front ends; single source of truth; existing tests stay. |

### Hosting alternatives considered and rejected

- **Render/Fly single FastAPI app** — cleanest reuse, but free tier sleeps
  (~50s cold start = blank page for a non-technical user); paid is ~$7/mo.
  Kept as a fallback if decks prove too large for serverless time limits.
- **Self-host on the M4 mini + Cloudflare Tunnel** — free and fully controlled,
  but goes down whenever the Mac sleeps/reboots. Too fragile for a "must always
  work" link.

## Architecture

All within the existing `github.com/ajaiupadhyaya/slidecheck` repo:

```
slidecheck/
  pptx_a11y/            # UNCHANGED engine (loader → checks → fixers → report)
    settings.py         #   + read ANTHROPIC_API_KEY from env (small addition)
    web/                # NEW: web-only glue (no Tkinter, no Vercel specifics)
      service.py        #   process uploaded bytes in a temp dir -> result + artifacts
  api/
    index.py            # NEW: FastAPI ASGI app exposed as a Vercel function
  public/               # NEW: static front end (one page)
    index.html
    app.js
    styles.css
  vercel.json           # NEW: routes + Python function config (maxDuration, memory)
  requirements.txt      # NEW: web/runtime deps ONLY (no tkinterdnd2)
```

The engine never imports Tkinter, so the web path imports only
`pipeline`/`checks`/`fixers`/`report`/`settings`/`alt_text_ai`. The Tkinter GUI
(`gui.py`) and its `tkinterdnd2` dependency are untouched and excluded from the
web runtime.

### Components

**`pptx_a11y/settings.py` (modified).** `get_describer` / settings loading also
honors the `ANTHROPIC_API_KEY` environment variable. Precedence: explicit
settings-file key (desktop) → `ANTHROPIC_API_KEY` env (web) → `NullDescriber`
(flag-only). The desktop app's behavior is unchanged because the env var is
absent there.

**`pptx_a11y/web/service.py` (new).** A thin, framework-agnostic adapter:
- Input: a filename + file bytes (one or many).
- Writes bytes into a fresh `tempfile.TemporaryDirectory`, calls
  `process_file(path, describer, out_dir=tmp)`, and returns per-file summaries.
  (The engine's `report.batch_index` writes filesystem-relative report links
  unsuitable for a stateless response, so the multi-file overview table is
  composed client-side from these per-file summaries instead.)
- Returns an in-memory result object: the `FileResult`(s), the rendered report
  HTML (already produced by the engine), and the bytes of the
  `_accessible.pptx` artifact(s).
- Guarantees temp-dir cleanup (context manager) so nothing persists.
- This is the unit that engine + web tests target; it knows nothing about HTTP.

**`api/index.py` (new).** FastAPI app, exported as `app` for Vercel's ASGI
Python runtime:
- `GET /api/health` — liveness.
- `POST /api/process` — multipart upload of one or more `.pptx` files; runs
  `web/service.py`; returns a **single stateless JSON response** carrying
  everything: per-file summary (counts of errors/warnings, auto-fixed count),
  the report HTML, and the fixed-`.pptx` + report bytes inline as base64. No
  second request and no server-side state — the response is self-contained.
- Password gate: every protected request must carry the shared secret
  (compared against the `SLIDECHECK_PASSWORD` env var). The front end collects
  it once and sends it with requests.
- Validation: reject non-`.pptx` extensions/content and uploads over the size
  cap (~50 MB) with friendly messages.

**`public/` (new).** One static page, framework-free (plain HTML/CSS/JS) for
minimal weight and zero build step:
- First load: a single password field (stored only in `sessionStorage`).
- Main view: a large drag-and-drop zone ("Drop your PowerPoint here to check it
  for accessibility") + a file picker fallback; accepts multiple files.
- Processing: a clear spinner with status text ("Checking… generating alt
  text…").
- Result: a friendly summary banner ("Found X issues — auto-fixed Y of them"),
  the engine's HTML report rendered inline, and prominent buttons **"Download
  fixed PowerPoint"** and **"Download report"** (built as in-browser Blob URLs
  from the base64 bytes already in the response — no server round-trip). Batch
  uploads show an overview table composed client-side from the per-file
  summaries.

**`vercel.json` (new).** Routes static assets from `public/`, routes `/api/*`
to the Python function, pins the Python runtime, and sets function
`maxDuration` to the plan maximum and adequate memory.

### Data flow

```
Browser (password + .pptx)
  → POST /api/process (multipart)
    → web/service.py: write bytes to TemporaryDirectory
      → process_file(): loader → checks → fixers (Claude alt text via env key) → HTML/JSON report
    → collect report HTML + fixed-pptx bytes in memory
    → TemporaryDirectory deleted (nothing persists)
  → single JSON: summary + report HTML + fixed-pptx/report bytes (base64)
Browser renders summary + report; download buttons build Blob URLs from the
base64 bytes already in hand.
```

The response is fully self-contained: no disk persistence, no database, no
second request, and no reliance on cross-invocation server memory (which Vercel
serverless does not guarantee).

### AI alt-text and serverless time limits

The fixer calls Claude vision once per embedded raster image (sequentially in
the current engine). A typical lecture deck (a handful to a few dozen images)
completes within the configured `maxDuration`. Mitigations, in order of
preference:

1. Set `maxDuration` to the plan maximum.
2. Cap the number of AI-described images per request; any beyond the cap are
   **flagged** (not auto-described) with a clear note, so the request always
   returns in time.
3. (Future, only if needed) Describe images concurrently to cut wall-clock to
   roughly the slowest single call.

The MVP uses (1) + (2). Concurrency (3) is explicitly deferred until a real
deck demonstrates it's needed.

### Error handling

- Non-`.pptx` upload → 400 with a plain-language message.
- Upload over size cap → 413 with the cap stated.
- Corrupt/unreadable deck → engine returns `FileResult.error`; surfaced as a
  friendly per-file error, other files still processed.
- Missing/invalid `ANTHROPIC_API_KEY` or Claude failure → engine degrades to
  flag-only (`NullDescriber` / per-call try/except already handle this); the
  report still renders and the fixed file is still produced for the
  non-AI fixers (titles, metadata).
- Wrong/absent password → 401; front end re-prompts.

### Testing

- **Engine tests:** unchanged (regression safety net).
- **`web/service.py` tests:** valid single + batch uploads produce a result with
  report HTML and fixed-pptx bytes; corrupt input surfaces as an error;
  temp dir is removed after processing (no leftover files).
- **`api/index.py` tests:** FastAPI `TestClient` — `/api/process` accepts a real
  `.pptx` fixture and returns the expected JSON shape; rejects non-pptx (400)
  and oversized (413); enforces the password gate (401); `ANTHROPIC_API_KEY`
  env path selects `ClaudeDescriber` (mocked) vs `NullDescriber`.
- **End-to-end:** after deploy, drive the live URL with Playwright — enter
  password, drop a fixture deck, assert the summary + report render and both
  download buttons return files.

## Success criteria

1. From a clean browser with no installed software, the user opens the URL,
   enters the shared password once, drops a `.pptx`, and downloads a fixed copy
   + a readable accessibility report.
2. Auto-alt-text works without the user supplying any key.
3. No uploaded file or result is persisted server-side after the response.
4. The desktop GUI, CLI, and all existing engine tests continue to pass
   unchanged.
5. The site is reachable without a cold-start wait on first visit.

## Rollout

- Build behind tests; deploy to Vercel from the existing GitHub repo
  (preview → production).
- Configure env vars in Vercel: `ANTHROPIC_API_KEY`, `SLIDECHECK_PASSWORD`.
- Optional: custom subdomain (e.g. `slidecheck.ajaiupadhyaya.com`).
- Hand the user the URL + password; README gains a short "Web app" section.
