"""
Main bot instance and initialization
"""
import logging
import discord
from discord.ext import commands
from typing import Optional

from core.config import settings
from core.database import init_database, close_database
from core.cache import init_cache, close_cache

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
        
        self.initial_extensions = [
            "commands.spirit_commands",
            "commands.weather_commands",
            "commands.social_commands",
            "commands.gaming_commands",
            "commands.world_commands",
            "commands.admin_commands",
        ]
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info("Setting up Sakura Spirit Bot...")
        
        # Initialize database and cache
        await init_database()
        await init_cache()
        
        # Load extensions
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
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
    
    async def close(self):
        """Called when the bot is shutting down"""
        logger.info("Shutting down Sakura Spirit Bot...")
        
        # Close database and cache connections
        await close_database()
        await close_cache()
        
        await super().close()


def create_bot() -> SakuraSpiritBot:
    """Factory function to create bot instance"""
    return SakuraSpiritBot()
