"""Read the bot probes from inside the beta network.

The bot publishes no port: it lives only on the internal network, so the probes
are read from a container in the same stack.

    Get-Content spacebar-beta\\spike\\probe.py | docker compose --env-file .env.spacebar `
        -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

Exit code 0 only when ``/ready`` answers HTTP 200.
"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8080"


def fetch(path: str) -> tuple[int, dict]:
    """Return the status code and the decoded body, including on 503."""
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> int:
    ready_status = 0
    for path in ("/health", "/ready"):
        status, body = fetch(path)
        print(f"{path} -> HTTP {status} {json.dumps(body, sort_keys=True)}")
        if path == "/ready":
            ready_status = status
    return 0 if ready_status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
