"""Complete the ``config.json`` that Spacebar generates on its first start.

Spacebar writes every endpoint as ``null`` and then refuses to boot until they
are set. This script fills the internal endpoints (container to container, used
by the bot) and the public ones (loopback, used by a browser client).

The gateway is the exception: ``GET /gateway/bot`` advertises
``gateway.endpointPublic`` and the bot reconnects to that URL, so it must be
reachable from inside the network. It therefore defaults to the internal address;
a browser client on Windows has to be pointed at ``ws://127.0.0.1:<port>/``
explicitly (``--gateway-advertised`` changes the advertised value).

Run it once, from the repository root, after the first ``up``:

    .\\.venv\\Scripts\\python.exe spacebar-beta\\init_config.py

The file is gitignored: it is runtime data, not source.
"""

import argparse
import json
import pathlib
import sys

DEFAULT_CONFIG = pathlib.Path("spacebar-beta/data/config.json")


def build_values(api_port: str, gateway_port: str, cdn_port: str, gateway_advertised: str) -> dict:
    """Return the endpoint values used by docker-compose.spacebar.yml."""
    return {
        ("general", "serverName"): f"http://127.0.0.1:{api_port}",
        ("api", "endpointPublic"): f"http://127.0.0.1:{api_port}/api/v9",
        ("api", "endpointPrivate"): "http://spacebar-api:3001/api/v9",
        ("cdn", "endpointPublic"): f"http://127.0.0.1:{cdn_port}/",
        ("cdn", "endpointPrivate"): "http://spacebar-cdn:3001/",
        ("gateway", "endpointPublic"): gateway_advertised,
        ("gateway", "endpointPrivate"): "ws://spacebar-gateway:3001/",
        ("rabbitmq", "host"): "amqp://guest:guest@rabbitmq:5672",
        ("register", "requireCaptcha"): False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG)
    parser.add_argument("--api-port", default="3002")
    parser.add_argument("--gateway-port", default="3001")
    parser.add_argument("--cdn-port", default="3003")
    parser.add_argument(
        "--gateway-advertised",
        default="ws://spacebar-gateway:3001/",
        help="URL returned by /gateway/bot; must be reachable by the bot",
    )
    args = parser.parse_args()

    if not args.config.is_file():
        print(f"missing {args.config}: start the stack once so Spacebar creates it")
        return 1

    config = json.loads(args.config.read_text(encoding="utf-8"))
    for (section, key), value in build_values(
        args.api_port, args.gateway_port, args.cdn_port, args.gateway_advertised
    ).items():
        config.setdefault(section, {})[key] = value

    args.config.write_text(json.dumps(config, indent=4), encoding="utf-8")
    print(f"updated {args.config}")
    print(f"  api      {config['api']['endpointPrivate']}")
    print(f"  gateway  {config['gateway']['endpointPrivate']}")
    print(f"  gateway  advertised {config['gateway']['endpointPublic']}")
    print(f"  cdn      {config['cdn']['endpointPrivate']}")
    print(f"  rabbitmq {config['rabbitmq']['host']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
