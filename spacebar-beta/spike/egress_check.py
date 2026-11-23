"""Prove that the beta bot container cannot reach external services.

Every target below must fail: the bot is attached only to the internal network,
so a configuration mistake cannot leak traffic to Discord or OpenAI.

    Get-Content spacebar-beta\\spike\\egress_check.py | docker compose --env-file .env.spacebar `
        -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

Exit code 0 when every external target is unreachable and the local stub answers.
"""

import json
import socket
import sys
import urllib.request

EXTERNAL_TARGETS = (
    ("discord.com", 443),
    ("gateway.discord.gg", 443),
    ("api.openai.com", 443),
)
LOCAL_STUB = "http://ai-mock:8081/health"


def main() -> int:
    failures = 0

    for host, port in EXTERNAL_TARGETS:
        try:
            with socket.create_connection((host, port), timeout=5):
                print(f"REACHABLE {host}:{port} -> FAIL (egress is open)")
                failures += 1
        except OSError as error:
            print(f"BLOCKED   {host}:{port} -> PASS ({type(error).__name__})")

    try:
        with urllib.request.urlopen(LOCAL_STUB, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
        print(f"LOCAL     {LOCAL_STUB} -> PASS ({body})")
    except OSError as error:
        print(f"LOCAL     {LOCAL_STUB} -> FAIL ({type(error).__name__}: {error})")
        failures += 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
