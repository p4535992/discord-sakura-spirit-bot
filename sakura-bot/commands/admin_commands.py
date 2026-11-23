"""
Administrative commands for server management
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands

from utils.embed_builder import SakuraEmbed
from core.database import get_db_session
from core.services import ServerService

logger = logging.getLogger(__name__)


class AdminCommands(commands.Cog):
    """Administrative commands"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="sakura-help", description="Display help information about Sakura Spirit Bot")
    async def help_command(self, interaction: discord.Interaction):
        """Display help information"""
        embed = SakuraEmbed.create_base(
            title="🌸 Sakura Spirit Bot - Help",
            description="Welcome to the Sakura Spirit Bot! Here are the available commands:",
            color=0xFFB7C5
        )
        
        # Core Commands
        embed.add_field(
            name="📋 Core Commands",
            value=(
                "`/sakura-help` - Show this help message\n"
                "`/sakura-profile` - View your profile\n"
                "`/sakura-server-info` - View server information"
            ),
            inline=False
        )
        
        # Spirit Commands
        embed.add_field(
            name="🌸 Spirit Commands",
            value=(
                "`/sakura-spirit-info` - View information about spirits\n"
                "`/sakura-my-spirit` - View your companion spirit\n"
                "`/sakura-spirit-interact` - Interact with your spirit"
            ),
            inline=False
        )
        
        # Weather Commands
        embed.add_field(
            name="🌤️ Weather Commands",
            value=(
                "`/sakura-weather` - Check current server weather\n"
                "`/sakura-weather-effects` - View weather effects"
            ),
            inline=False
        )
        
        # Social Commands
        embed.add_field(
            name="💫 Social Commands",
            value=(
                "`/sakura-send-gift` - Send a gift to another user\n"
                "`/sakura-daily-dream` - View your daily dream\n"
                "`/sakura-relationships` - View your relationships"
            ),
            inline=False
        )
        
        # Gaming Commands
        embed.add_field(
            name="🎮 Gaming Commands",
            value=(
                "`/sakura-lfg` - Look for group\n"
                "`/sakura-ritual-buff` - Perform pre-game ritual"
            ),
            inline=False
        )
        
        # World Commands
        embed.add_field(
            name="🗺️ World Commands",
            value=(
                "`/sakura-explore` - Explore Sakura Park\n"
                "`/sakura-shop` - Visit the shop\n"
                "`/sakura-quests` - View available quests"
            ),
            inline=False
        )
        
        # Gacha Commands
        embed.add_field(
            name="🎰 Gacha Commands",
            value=(
                "`/sakura-gacha-pull` - Pull from the gacha\n"
                "`/sakura-inventory` - View your inventory"
            ),
            inline=False
        )
        
        # Admin Commands
        embed.add_field(
            name="⚙️ Admin Commands",
            value=(
                "`/sakura-admin-toggle-feature` - Enable/disable features\n"
                "`/sakura-admin-set-weather` - Manually set weather\n"
                "`/sakura-admin-stats` - View bot statistics"
            ),
            inline=False
        )
        
        embed.set_footer(text="All commands start with /sakura-")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-profile", description="View your Sakura Spirit profile")
    async def profile(self, interaction: discord.Interaction):
        """Display user profile"""
        async with get_db_session() as session:
            from core.services import UserService
            
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            xp_needed = user.xp_for_next_level()
            
            embed = SakuraEmbed.user_profile(
                username=interaction.user.name,
                level=user.level,
                xp=user.xp,
                xp_needed=xp_needed,
                emotional_state=user.emotional_state,
                currency=user.currency,
                aura=user.aura_type
            )
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-server-info", description="View server information")
    async def server_info(self, interaction: discord.Interaction):
        """Display server information"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server!")
            return
        
        async with get_db_session() as session:
            server = await ServerService.get_or_create_server(
                session,
                interaction.guild.id,
                interaction.guild.name
            )
            
            embed = SakuraEmbed.create_base(
                title=f"🌸 {interaction.guild.name}",
                description="Server information and status",
                color=0xFFB7C5
            )
            
            embed.add_field(name="🎭 Harmony Score", value=f"{server.harmony_score:.1f}/100", inline=True)
            embed.add_field(name="🌤️ Current Weather", value=server.current_weather, inline=True)
            embed.add_field(name="⚔️ Dominant Faction", value=server.faction_dominance, inline=True)
            
            # Feature status
            features = server.enabled_features or {}
            enabled_features = [k.title() for k, v in features.items() if v]
            
            if enabled_features:
                embed.add_field(
                    name="✨ Enabled Features",
                    value=", ".join(enabled_features),
                    inline=False
                )
            
            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.set_footer(text=f"Server ID: {interaction.guild.id}")
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-admin-toggle-feature", description="Enable or disable a bot feature")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(feature="The feature to toggle", enabled="Enable or disable")
    async def toggle_feature(
        self,
        interaction: discord.Interaction,
        feature: str,
        enabled: bool
    ):
        """Toggle a bot feature for the server"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server!")
            return
        
        valid_features = ["spirits", "weather", "social", "gaming", "world", "gacha", "events"]
        
        if feature.lower() not in valid_features:
            await interaction.response.send_message(
                f"❌ Invalid feature. Valid options: {', '.join(valid_features)}"
            )
            return
        
        async with get_db_session() as session:
            server = await ServerService.get_or_create_server(
                session,
                interaction.guild.id,
                interaction.guild.name
            )
            
            if not server.enabled_features:
                server.enabled_features = {}
            
            server.enabled_features[feature.lower()] = enabled
            await session.commit()
            
            status = "enabled" if enabled else "disabled"
            embed = SakuraEmbed.success(
                f"Feature **{feature.title()}** has been **{status}** for this server."
            )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-admin-set-weather", description="Manually set the server weather")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(weather="The weather type to set")
    async def set_weather(self, interaction: discord.Interaction, weather: str):
        """Manually set server weather"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server!")
            return
        
        from core.config import settings
        
        if weather not in settings.weather_types:
            await interaction.response.send_message(
                f"❌ Invalid weather type. Valid options: {', '.join(settings.weather_types)}"
            )
            return
        
        async with get_db_session() as session:
            server = await ServerService.get_or_create_server(
                session,
                interaction.guild.id,
                interaction.guild.name
            )
            
            await ServerService.change_weather(session, server, weather)
            
            embed = SakuraEmbed.weather_update(
                weather_type=weather,
                description=f"The weather has been manually changed to **{weather}**",
                effects=["Weather effects are now active"],
                duration="Until next change"
            )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-admin-stats", description="View bot statistics")
    @app_commands.default_permissions(administrator=True)
    async def show_admin_stats(self, interaction: discord.Interaction):
        """Display bot statistics"""
        embed = SakuraEmbed.create_base(
            title="📊 Bot Statistics",
            description="Current bot status and statistics",
            color=0xFFB7C5
        )
        
        embed.add_field(name="🌐 Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="👥 Users", value=str(len(self.bot.users)), inline=True)
        embed.add_field(name="📝 Commands", value=str(len(self.bot.tree.get_commands())), inline=True)
        
        # Latency
        latency_ms = round(self.bot.latency * 1000)
        embed.add_field(name="⚡ Latency", value=f"{latency_ms}ms", inline=True)
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(AdminCommands(bot))
    logger.info("AdminCommands cog loaded")
