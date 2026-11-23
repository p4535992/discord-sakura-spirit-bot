"""
Main bot instance and initialization
"""
import logging
import discord
from discord.ext import commands

from core.config import settings
from core.database import init_database, close_database
from core.cache import init_cache, close_cache
from core.health import health_server

logger = logging.getLogger(__name__)


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
        
        # Initialize database and cache before any extension uses them.
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
        # Readiness may turn true only now: the extension loading is over.
        health_server.bootstrap_complete = True
        
        if self.startup_failures and settings.strict_startup:
            raise RuntimeError(
                "Required extensions failed to load: " + ", ".join(self.startup_failures)
            )
        
        # Sync slash commands only when the command tree is complete.
        try:
            synced = await self.tree.sync()
            logger.info("Synced %s slash commands", len(synced))
        except Exception:
            logger.exception("Failed to sync slash commands")
            if settings.strict_startup:
                raise
    
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
        logger.error("Unhandled slash command error", exc_info=error)
        message = "❌ An unexpected error occurred. Please try again later."
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
