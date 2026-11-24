"""
Main entry point for Sakura Spirit Bot
"""
import asyncio
import logging
import sys

import colorlog

from core.ai_provider import AIProviderConfigurationError, validate_ai_provider
from core.config import settings
from core.bot import create_bot
from core.platform import PlatformConfigurationError, apply_platform_overrides


def setup_logging():
    """Configure logging on stdout/stderr only.

    Docker captures the stream and rotates it with the ``json-file`` driver
    (``max-size``/``max-file`` in the Compose files), so the application keeps no
    log file, no log volume and no logrotate sidecar. The handler is added once:
    a second call (tests, restart in the same interpreter) must not duplicate
    every line.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    if not any(getattr(handler, "_sakura_console", False) for handler in root_logger.handlers):
        console_handler = colorlog.StreamHandler()
        console_handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s %(message)s",
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
        )
        # Marker used by the guard above to recognise its own handler.
        console_handler._sakura_console = True
        root_logger.addHandler(console_handler)
    
    # Reduce discord.py logging noise
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)


async def main():
    """Main async function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("🌸 Starting Sakura Spirit Bot 🌸")
    logger.info("=" * 60)
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Platform: {settings.platform}")
    logger.info(f"AI provider: {settings.ai_provider}")
    logger.info(f"Prefix: {settings.bot_prefix}")
    logger.info(f"Features enabled: Spirits={settings.enable_spirits}, Weather={settings.enable_weather}")

    # Validate the AI backend before the login: a beta must never reach a
    # provider it did not intend to use, and an unknown value must not be
    # discovered halfway through a command.
    try:
        validate_ai_provider(settings)
    except AIProviderConfigurationError as error:
        logger.critical(f"Invalid AI provider configuration: {error}")
        sys.exit(1)

    # Redirect the transport before the client exists: the REST base and the
    # gateway must be in place before the first call, and an invalid platform
    # configuration must stop the process instead of reaching another service.
    try:
        apply_platform_overrides(settings)
    except PlatformConfigurationError as error:
        logger.critical(f"Invalid platform configuration: {error}")
        sys.exit(1)

    bot = create_bot()
    
    try:
        async with bot:
            await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🌸 Sakura Spirit Bot stopped gracefully 🌸")
