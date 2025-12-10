"""
Event-related commands (rituals, world bosses)
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands

from utils.embed_builder import SakuraEmbed

logger = logging.getLogger(__name__)


class EventCommands(commands.Cog):
    """Commands for server-wide events"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rituals", description="View or start a cooperative ritual")
    async def rituals(self, interaction: discord.Interaction):
        """Display ritual information"""
        embed = SakuraEmbed.info(
            "Rituals - Coming Soon!",
            "This feature is currently under development. Soon you'll be able to join others in powerful rituals!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="world-boss", description="Check the status of the world boss")
    async def world_boss(self, interaction: discord.Interaction):
        """Display world boss information"""
        embed = SakuraEmbed.info(
            "World Boss - Coming Soon!",
            "This feature is currently under development. Prepare for epic battles against powerful foes!"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(EventCommands(bot))
    logger.info("EventCommands cog loaded")
