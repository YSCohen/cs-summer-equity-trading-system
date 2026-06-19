FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY . .

RUN adduser \
    --uid 5678 \
    --disabled-password \
    --gecos "" \
    appuser \
    && chown -R appuser /app

USER appuser

CMD ["uv", "run", "main.py"]