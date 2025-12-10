"""
Weather-related commands
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands

from utils.embed_builder import SakuraEmbed
from core.database import get_db_session
from core.services import ServerService
from systems.weather.weather_engine import WeatherEngine, WeatherType

logger = logging.getLogger(__name__)


class WeatherCommands(commands.Cog):
    """Commands for weather system"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="weather", description="Check the current server weather")
    async def weather(self, interaction: discord.Interaction):
        """Display current weather"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server!")
            return
        
        async with get_db_session() as session:
            server = await ServerService.get_or_create_server(
                session,
                interaction.guild.id,
                interaction.guild.name
            )
            
            weather_type = server.current_weather
            weather_info = WeatherType.get_weather_info(weather_type)
            
            # Format effects
            effects = WeatherEngine.format_weather_effects(weather_type)
            
            # Calculate time since change
            from datetime import datetime
            time_since = datetime.utcnow() - server.weather_changed_at
            hours = int(time_since.total_seconds() // 3600)
            minutes = int((time_since.total_seconds() % 3600) // 60)
            
            duration_text = f"{hours}h {minutes}m ago" if hours > 0 else f"{minutes}m ago"
            
            embed = SakuraEmbed.weather_update(
                weather_type=weather_type,
                description=weather_info.get("description", ""),
                effects=effects,
                duration=f"Changed {duration_text}"
            )
            
            embed.add_field(
                name="🎭 Server Harmony",
                value=f"{server.harmony_score:.1f}/100",
                inline=True
            )
            
            embed.add_field(
                name="⚔️ Dominant Faction",
                value=server.faction_dominance,
                inline=True
            )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="weather-effects", description="View detailed weather effects")
    async def weather_effects(self, interaction: discord.Interaction):
        """Display detailed weather effects"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server!")
            return
        
        async with get_db_session() as session:
            server = await ServerService.get_or_create_server(
                session,
                interaction.guild.id,
                interaction.guild.name
            )
            
            weather_type = server.current_weather
            weather_info = WeatherType.get_weather_info(weather_type)
            effects = weather_info.get("effects", {})
            
            embed = SakuraEmbed.create_base(
                title=f"{weather_info.get('emoji', '🌸')} {weather_type} - Effects",
                description=weather_info.get("description", ""),
                color=0xFFB7C5
            )
            
            # XP Multiplier
            if "xp_multiplier" in effects:
                multiplier = effects["xp_multiplier"]
                percentage = int((multiplier - 1.0) * 100)
                embed.add_field(
                    name="📊 XP Gain",
                    value=f"{'+'if percentage > 0 else ''}{percentage}% ({multiplier}x)",
                    inline=True
                )
            
            # Gacha Luck
            if "gacha_luck" in effects:
                multiplier = effects["gacha_luck"]
                percentage = int((multiplier - 1.0) * 100)
                embed.add_field(
                    name="🎰 Gacha Luck",
                    value=f"{'+'if percentage > 0 else ''}{percentage}% ({multiplier}x)",
                    inline=True
                )
            
            # Currency Gain
            if "currency_gain" in effects:
                multiplier = effects["currency_gain"]
                percentage = int((multiplier - 1.0) * 100)
                embed.add_field(
                    name="💰 Currency Gain",
                    value=f"{'+'if percentage > 0 else ''}{percentage}% ({multiplier}x)",
                    inline=True
                )
            
            # Spirit Activity
            if "spirit_activity" in effects:
                activity = effects["spirit_activity"]
                embed.add_field(
                    name="🌸 Spirit Activity",
                    value=activity.replace("_", " ").title(),
                    inline=True
                )
            
            # Event Spawn Rate
            if "event_spawn_rate" in effects:
                rate = effects["event_spawn_rate"]
                embed.add_field(
                    name="🎊 Event Spawn Rate",
                    value=f"{rate}x normal",
                    inline=True
                )
            
            # Special Effects
            special_effects = []
            if "harmony_boost" in effects:
                special_effects.append("• Harmony boost active")
            if "dream_quality" in effects:
                special_effects.append(f"• Dream quality: {effects['dream_quality']}")
            if "secret_discovery" in effects:
                special_effects.append(f"• Secret discovery: {effects['secret_discovery']}x")
            if "random_events" in effects:
                special_effects.append("• Random events may occur!")
            
            if special_effects:
                embed.add_field(
                    name="✨ Special Effects",
                    value="\n".join(special_effects),
                    inline=False
                )
            
            embed.add_field(
                name="🎭 Rarity",
                value=weather_info.get("rarity", "common").title(),
                inline=True
            )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="weather-history", description="View recent weather changes")
    async def weather_history(self, interaction: discord.Interaction):
        """Display weather history"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server!")
            return
        
        async with get_db_session() as session:
            server = await ServerService.get_or_create_server(
                session,
                interaction.guild.id,
                interaction.guild.name
            )
            
            history = await WeatherEngine.get_weather_history(session, server.id, limit=5)
            
            if not history:
                embed = SakuraEmbed.info("Weather History", "No weather history available yet.")
                await interaction.response.send_message(embed=embed)
                return
            
            embed = SakuraEmbed.create_base(
                title="🌤️ Weather History",
                description="Recent weather changes in this server",
                color=0xFFB7C5
            )
            
            for record in history:
                weather_info = WeatherType.get_weather_info(record.weather_type)
                emoji = weather_info.get("emoji", "🌸")
                
                # Calculate duration
                if record.ended_at:
                    duration = record.ended_at - record.started_at
                    hours = int(duration.total_seconds() // 3600)
                    minutes = int((duration.total_seconds() % 3600) // 60)
                    duration_text = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                else:
                    duration_text = "Current"
                
                # Format timestamp
                timestamp = record.started_at.strftime("%m/%d %H:%M")
                
                embed.add_field(
                    name=f"{emoji} {record.weather_type}",
                    value=f"Started: {timestamp}\nDuration: {duration_text}",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="weather-list", description="View all possible weather types")
    async def weather_list(self, interaction: discord.Interaction):
        """Display all weather types"""
        embed = SakuraEmbed.create_base(
            title="🌤️ All Weather Types",
            description="Discover the various weather phenomena in the Sakura realm",
            color=0xFFB7C5
        )
        
        # Group by rarity
        weather_by_rarity = {
            "common": [],
            "uncommon": [],
            "rare": [],
            "epic": [],
            "legendary": []
        }
        
        for weather_type in WeatherType.get_all_weather_types():
            weather_info = WeatherType.get_weather_info(weather_type)
            rarity = weather_info.get("rarity", "common")
            emoji = weather_info.get("emoji", "🌸")
            
            weather_by_rarity[rarity].append(f"{emoji} {weather_type}")
        
        # Add fields for each rarity
        rarity_order = ["common", "uncommon", "rare", "epic", "legendary"]
        rarity_emojis = {
            "common": "⚪",
            "uncommon": "🟢",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡"
        }
        
        for rarity in rarity_order:
            if weather_by_rarity[rarity]:
                embed.add_field(
                    name=f"{rarity_emojis[rarity]} {rarity.title()}",
                    value="\n".join(weather_by_rarity[rarity]),
                    inline=False
                )
        
        embed.set_footer(text="Use /weather-effects to see detailed effects of current weather")
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(WeatherCommands(bot))
    logger.info("WeatherCommands cog loaded")
