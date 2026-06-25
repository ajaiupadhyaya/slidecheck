# SlideCheck web app — runs the FastAPI app (api/index.py) as a long-lived
# uvicorn server. Used by Fly.io. Unlike a serverless host, there is no request
# body-size cap or function timeout here, so large image-heavy decks and the AI
# alt-text pass work without special handling.
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code only: the accessibility engine, the API, and the static front end.
# (tests/, docs/, packaging/, the desktop GUI's tkinter dep, etc. are excluded.)
COPY pptx_a11y ./pptx_a11y
COPY api ./api
COPY public ./public

# Fly provides $PORT (defaults to 8080). Bind all interfaces.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn api.index:app --host 0.0.0.0 --port ${PORT:-8080}"]
