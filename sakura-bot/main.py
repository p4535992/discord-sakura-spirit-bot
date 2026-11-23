"""
Main entry point for Sakura Spirit Bot
"""
import asyncio
import logging
import sys
from pathlib import Path

import colorlog

from core.config import settings
from core.bot import create_bot
from core.platform import PlatformConfigurationError, apply_platform_overrides


def setup_logging():
    """Configure logging with colors"""
    # Create the directory that owns the configured log file.
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Console handler with colors
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
    
    # File handler
    file_handler = logging.FileHandler(settings.log_file, encoding='utf-8')
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
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
    logger.info(f"Prefix: {settings.bot_prefix}")
    logger.info(f"Features enabled: Spirits={settings.enable_spirits}, Weather={settings.enable_weather}")

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
