# Local OpenAI-compatible stub used by the Spacebar beta stack.
# Only the standard library is needed, so no package download happens at build.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Rome

WORKDIR /app

COPY app.py ./

RUN useradd --create-home --uid 10002 mock \
    && chown -R mock:mock /app

USER mock

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=3)"

CMD ["python", "app.py"]
