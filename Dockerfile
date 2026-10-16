# Single-container deployment (e.g. Render): the API also serves the built website.
#   docker build -t pathtopro . && docker run -p 8000:8000 -e PATHTOPRO_AUTOSEED=on ... pathtopro

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATHTOPRO_ENV=production \
    PATHTOPRO_STATIC_DIR=/app/static
WORKDIR /app
COPY backend/ ./
# Editable install: the code runs from /app, next to its config/ files.
RUN pip install --no-cache-dir -e . && useradd --create-home app && chown -R app /app
COPY --from=web --chown=app /web/dist ./static
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
