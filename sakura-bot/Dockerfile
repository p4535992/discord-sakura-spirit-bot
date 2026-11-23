# Multi-stage build: compilers stay in the builder, the runtime image only
# carries the virtual environment and the application sources.
#
# Build from the repository root, because the context must contain the
# application sources:
#   docker build -f sakura-bot/Dockerfile -t sakura-spirit-bot:local .
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build tooling is needed only if a dependency has no wheel for this platform.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    TZ=Europe/Rome

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY main.py ./
COPY core ./core
COPY commands ./commands
COPY models ./models
COPY systems ./systems
COPY utils ./utils

# Unprivileged runtime user; the log directory is created here so a named
# volume inherits the correct ownership.
RUN useradd --create-home --uid 10001 sakura \
    && mkdir -p /var/log/sakura-bot \
    && chown -R sakura:sakura /app /var/log/sakura-bot

USER sakura

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4)"

CMD ["python", "main.py"]
