FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml ./
COPY . .
# Editable install: the code runs from /app, next to its config/ files.
RUN pip install --no-cache-dir -e . && useradd -m app && chown -R app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
