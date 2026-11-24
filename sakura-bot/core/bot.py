"""
Main bot instance and initialization
"""
import logging
from typing import Optional

import discord
from discord.ext import commands

from core.config import is_discord_beta, settings
from core.database import init_database, close_database
from core.cache import init_cache, close_cache
from core.health import health_server

logger = logging.getLogger(__name__)


def resolve_command_sync_guild() -> Optional[discord.Object]:
    """Return the guild that must receive the commands, or ``None`` for a global sync.

    Only ``SAKURA_BOT_ENVIRONMENT=discord-beta`` narrows the scope: the
    production deployment keeps the global sync even when the variable is left
    in the environment. A beta without its guild ID fails closed instead of
    publishing the commands globally.
    """
    if not is_discord_beta():
        return None
    if not settings.test_guild_id:
        logger.error(
            "Discord beta selected without SAKURA_BOT_TEST_GUILD_ID: refusing to sync globally"
        )
        raise RuntimeError(
            "SAKURA_BOT_TEST_GUILD_ID is required when SAKURA_BOT_ENVIRONMENT=discord-beta"
        )
    return discord.Object(id=settings.test_guild_id)


class SakuraSpiritBot(commands.Bot):
    """Main Sakura Spirit Bot class"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix=settings.bot_prefix,
            intents=intents,
            help_command=None,  # Custom help command
        )
        
        # Extensions that must load for the bot to be considered healthy.
        self.required_extensions = [
            "commands.spirit_commands",
            "commands.weather_commands",
            "commands.social_commands",
            "commands.gaming_commands",
            "commands.world_commands",
            "commands.admin_commands",
        ]
        # Present in the repository but intentionally not loaded yet:
        # ``commands.gacha_commands`` and ``commands.events_commands`` expose
        # unfinished or "coming soon" behaviour, so enabling them is a product
        # decision and not a side effect of the bootstrap.
        self.optional_extensions: list[str] = []
        self.startup_failures: list[str] = []
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info("Setting up Sakura Spirit Bot...")
        
        # Initialize the database and the in-process cache before any extension
        # uses them: the cache holds only rebuildable data, the database holds
        # the state that must survive a restart.
        await init_database()
        await init_cache()
        # The readiness probe needs the client instance to report the gateway
        # state, so it is attached before the HTTP server starts.
        health_server.attach(self)
        await health_server.start()
        
        for extension in self.required_extensions:
            try:
                await self.load_extension(extension)
                logger.info("Loaded extension: %s", extension)
            except Exception:
                logger.exception("Required extension failed to load: %s", extension)
                self.startup_failures.append(extension)
        
        for extension in self.optional_extensions:
            try:
                await self.load_extension(extension)
                logger.info("Loaded optional extension: %s", extension)
            except Exception:
                logger.exception("Optional extension failed to load: %s", extension)
        
        health_server.startup_failures = self.startup_failures
        
        if self.startup_failures and settings.strict_startup:
            raise RuntimeError(
                "Required extensions failed to load: " + ", ".join(self.startup_failures)
            )
        
        # Resolve the sync target before the try block: a beta without its guild
        # ID must stop the startup even when ``strict_startup`` is false.
        sync_guild = resolve_command_sync_guild()

        # Sync slash commands only when the command tree is complete.
        try:
            synced = await self._sync_application_commands(sync_guild)
            logger.info("Synced %s slash commands", len(synced))
        except Exception:
            logger.exception("Failed to sync slash commands")
            if settings.strict_startup:
                raise

        # Readiness may turn true only now: the extensions are loaded and the
        # command tree has been synchronised (or the failure was tolerated).
        health_server.bootstrap_complete = True

    async def _sync_application_commands(self, guild: Optional[discord.Object]) -> list:
        """Upload the command tree globally or to the single ``guild``."""
        if guild is None:
            return await self.tree.sync()
        # ``copy_global_to`` duplicates the global tree into the guild scope,
        # which is what makes the commands appear there immediately.
        self.tree.copy_global_to(guild=guild)
        return await self.tree.sync(guild=guild)
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="cherry blossoms fall 🌸"
        )
        await self.change_presence(activity=activity)
        
        logger.info("Sakura Spirit Bot is ready!")
    
    async def on_guild_join(self, guild: discord.Guild):
        """Called when the bot joins a new guild"""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Initialize server in database
        from models import Server
        from core.database import get_db_session
        
        async with get_db_session() as session:
            # Check if server already exists
            from sqlalchemy import select
            result = await session.execute(
                select(Server).where(Server.discord_id == guild.id)
            )
            existing_server = result.scalar_one_or_none()
            
            if not existing_server:
                new_server = Server(
                    discord_id=guild.id,
                    name=guild.name,
                    harmony_score=50.0,
                    current_weather="Gentle Breeze",
                    enabled_features={
                        "spirits": settings.enable_spirits,
                        "weather": settings.enable_weather,
                        "social": settings.enable_social,
                        "gaming": settings.enable_gaming,
                        "world": settings.enable_world,
                        "gacha": settings.enable_gacha,
                        "events": settings.enable_events,
                    }
                )
                session.add(new_server)
                await session.commit()
                logger.info(f"Initialized server {guild.name} in database")
    
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
            return
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ This command is on cooldown. Try again in {error.retry_after:.1f}s")
            return
        
        # Log unexpected errors
        logger.error(f"Unhandled command error: {error}", exc_info=error)
        await ctx.send("❌ An unexpected error occurred. Please try again later.")
    
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        """Answer failed slash commands instead of leaving the interaction pending."""
        if isinstance(error, discord.app_commands.NoPrivateMessage):
            await self._answer_failed_command(
                interaction, "❌ This command can only be used in a server."
            )
            return

        if isinstance(error, discord.app_commands.MissingPermissions):
            # ``has_permissions`` reads ``interaction.permissions``, which is
            # empty in a direct message: report the real reason there.
            if interaction.guild is None:
                message = "❌ This command can only be used in a server."
            else:
                message = "❌ You need the Administrator permission to use this command."
            await self._answer_failed_command(interaction, message)
            return

        logger.error("Unhandled slash command error", exc_info=error)
        await self._answer_failed_command(
            interaction, "❌ An unexpected error occurred. Please try again later."
        )

    async def _answer_failed_command(self, interaction: discord.Interaction, message: str):
        """Deliver an ephemeral failure message without raising a second error."""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.warning("Unable to deliver the slash command error message", exc_info=True)
    
    async def close(self):
        """Called when the bot is shutting down"""
        logger.info("Shutting down Sakura Spirit Bot...")
        
        # Stop the health endpoint first so probes fail fast during shutdown.
        await health_server.stop()
        await close_database()
        await close_cache()
        
        await super().close()


def create_bot() -> SakuraSpiritBot:
    """Factory function to create bot instance"""
    return SakuraSpiritBot()
