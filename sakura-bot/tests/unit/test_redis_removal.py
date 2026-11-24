"""Static guard against the infrastructure removed by the cache migration.

The migration replaced Redis with an in-process cache and removed Traefik and
the logrotate sidecar from the active stacks. Their source folders
(``sakura-redis/``, ``sakura-proxy/``, ``sakura-proxy-logrotate/``) were deleted
once nothing referenced them, so this module asserts both the active
configuration and the absence of those folders. Comment lines are ignored: they
may legitimately document what was removed.
"""

import os
from pathlib import Path

# The Docker test runner mounts only the repository files it needs, so the clone
# root is passed explicitly there; on the host it is derived from this file.
REPOSITORY_ROOT = Path(
    os.environ.get("SAKURA_REPOSITORY_ROOT") or Path(__file__).resolve().parents[3]
)
APPLICATION_ROOT = Path(__file__).resolve().parents[2]

ACTIVE_COMPOSE_FILES = (
    "docker-compose.yml",
    "docker-compose.discord-beta.yml",
    "docker-compose.spacebar.yml",
    "docker-compose.sakura-local-test.yml",
)

ENV_TEMPLATES = (
    ".env.example",
    ".env.discord-beta.example",
    ".env.spacebar.example",
    ".env.sakura-local-test",
)

# Source folders deleted with the migration: no copy may reappear as a backup.
REMOVED_FOLDERS = ("sakura-redis", "sakura-proxy", "sakura-proxy-logrotate")

# Built at runtime so this file does not match its own needles.
REDIS_IMPORT_NEEDLES = ("import " + "redis", "from " + "redis")
FILE_HANDLER_NEEDLE = "File" + "Handler"
LOG_FILE_NEEDLE = "LOG_" + "FILE"


def _active_lines(path: Path) -> list[str]:
    """Return the non-comment, non-blank lines of a configuration file."""
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_no_python_module_imports_the_redis_client():
    offenders = []
    for path in APPLICATION_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in REDIS_IMPORT_NEEDLES):
            offenders.append(path.relative_to(APPLICATION_ROOT).as_posix())

    assert offenders == []


def test_requirements_do_not_pin_a_redis_client():
    requirements = (APPLICATION_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "redis==" not in requirements


def test_the_application_writes_no_log_file():
    main_source = (APPLICATION_ROOT / "main.py").read_text(encoding="utf-8")

    assert FILE_HANDLER_NEEDLE not in main_source
    assert "log_file" not in main_source


def test_active_compose_files_declare_no_removed_service():
    forbidden = (
        "sakura-redis",
        "beta-redis",
        "redis-test",
        "sakura-proxy",
        "logrotate",
        "traefik",
    )
    for name in ACTIVE_COMPOSE_FILES:
        text = "\n".join(_active_lines(REPOSITORY_ROOT / name))
        for token in forbidden:
            assert token not in text, f"{name} still references {token}"


def test_env_templates_do_not_configure_removed_infrastructure():
    forbidden = ("REDIS", "PROXY", "LOGROTATE", LOG_FILE_NEEDLE)
    for name in ENV_TEMPLATES:
        text = "\n".join(_active_lines(REPOSITORY_ROOT / name))
        for token in forbidden:
            assert token not in text, f"{name} still configures {token}"


def test_removed_infrastructure_folders_are_gone():
    """The legacy source folders were deleted, not only unwired from Compose."""
    for name in REMOVED_FOLDERS:
        assert not (REPOSITORY_ROOT / name).exists(), f"{name} is back in the tree"
