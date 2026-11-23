"""
Aesthetic embed templates for Sakura Spirit Bot
"""
import discord
from datetime import datetime
from typing import Optional, List


class EmbedColors:
    """Sakura-themed color palette"""
    SAKURA_PINK = 0xFFB7C5
    CHERRY_BLOSSOM = 0xFFDAE9
    MOONLIGHT = 0xE6E6FA
    STORM_PURPLE = 0x9370DB
    GOLDEN_HOUR = 0xFFD700
    TWILIGHT = 0x8B7D9B
    CRIMSON = 0xDC143C
    FROST = 0xB0E0E6
    SUCCESS = 0x90EE90
    ERROR = 0xFF6B6B
    WARNING = 0xFFD93D


class SakuraEmbed:
    """Builder for aesthetic Sakura-themed embeds"""
    
    @staticmethod
    def create_base(
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: int = EmbedColors.SAKURA_PINK
    ) -> discord.Embed:
        """Create a base embed with Sakura styling"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        return embed
    
    @staticmethod
    def spirit_profile(
        spirit_name: str,
        rarity: str,
        faction: str,
        power_level: int,
        mood: str,
        description: Optional[str] = None
    ) -> discord.Embed:
        """Create a spirit profile embed"""
        rarity_colors = {
            "common": EmbedColors.FROST,
            "uncommon": EmbedColors.SUCCESS,
            "rare": EmbedColors.SAKURA_PINK,
            "epic": EmbedColors.STORM_PURPLE,
            "legendary": EmbedColors.GOLDEN_HOUR
        }
        
        embed = SakuraEmbed.create_base(
            title=f"🌸 {spirit_name}",
            description=description or "A mystical spirit of the Sakura realm",
            color=rarity_colors.get(rarity.lower(), EmbedColors.SAKURA_PINK)
        )
        
        embed.add_field(name="✨ Rarity", value=rarity.title(), inline=True)
        embed.add_field(name="⚔️ Faction", value=faction, inline=True)
        embed.add_field(name="💪 Power", value=str(power_level), inline=True)
        embed.add_field(name="😊 Mood", value=mood, inline=True)
        
        return embed
    
    @staticmethod
    def weather_update(
        weather_type: str,
        description: str,
        effects: List[str],
        duration: Optional[str] = None
    ) -> discord.Embed:
        """Create a weather update embed"""
        weather_colors = {
            "Petal Storm": EmbedColors.SAKURA_PINK,
            "Lunar Bloom": EmbedColors.MOONLIGHT,
            "Eclipse": EmbedColors.TWILIGHT,
            "Mistfall": EmbedColors.FROST,
            "Crimson Dawn": EmbedColors.CRIMSON,
            "Thunder Blossom": EmbedColors.STORM_PURPLE,
            "Golden Hour": EmbedColors.GOLDEN_HOUR,
        }
        
        embed = SakuraEmbed.create_base(
            title=f"🌤️ Weather Change: {weather_type}",
            description=description,
            color=weather_colors.get(weather_type, EmbedColors.SAKURA_PINK)
        )
        
        if effects:
            effects_text = "\n".join([f"• {effect}" for effect in effects])
            embed.add_field(name="✨ Effects", value=effects_text, inline=False)
        
        if duration:
            embed.add_field(name="⏰ Duration", value=duration, inline=False)
        
        embed.set_footer(text="The winds of change blow through the server")
        
        return embed
    
    @staticmethod
    def user_profile(
        username: str,
        level: int,
        xp: int,
        xp_needed: int,
        emotional_state: str,
        currency: int,
        aura: Optional[str] = None
    ) -> discord.Embed:
        """Create a user profile embed"""
        embed = SakuraEmbed.create_base(
            title=f"🌸 {username}'s Profile",
            color=EmbedColors.CHERRY_BLOSSOM
        )
        
        # Progress bar
        progress = int((xp / xp_needed) * 10)
        progress_bar = "█" * progress + "░" * (10 - progress)
        
        embed.add_field(name="📊 Level", value=str(level), inline=True)
        embed.add_field(name="💰 Currency", value=str(currency), inline=True)
        embed.add_field(name="💫 Emotional State", value=emotional_state, inline=True)
        
        if aura:
            embed.add_field(name="✨ Aura", value=aura, inline=True)
        
        embed.add_field(
            name="🎯 XP Progress",
            value=f"{progress_bar} {xp}/{xp_needed}",
            inline=False
        )
        
        return embed
    
    @staticmethod
    def level_up(username: str, new_level: int) -> discord.Embed:
        """Create a level up notification embed"""
        embed = SakuraEmbed.create_base(
            title="🎉 Level Up!",
            description=f"**{username}** has reached **Level {new_level}**!",
            color=EmbedColors.GOLDEN_HOUR
        )
        
        embed.set_footer(text="Your spirit grows stronger with each blossom")
        
        return embed
    
    @staticmethod
    def gacha_result(
        item_name: str,
        item_type: str,
        rarity: str,
        description: Optional[str] = None
    ) -> discord.Embed:
        """Create a gacha pull result embed"""
        rarity_colors = {
            "common": EmbedColors.FROST,
            "uncommon": EmbedColors.SUCCESS,
            "rare": EmbedColors.SAKURA_PINK,
            "epic": EmbedColors.STORM_PURPLE,
            "legendary": EmbedColors.GOLDEN_HOUR
        }
        
        rarity_emojis = {
            "common": "⚪",
            "uncommon": "🟢",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡"
        }
        
        embed = SakuraEmbed.create_base(
            title=f"{rarity_emojis.get(rarity.lower(), '✨')} {item_name}",
            description=description or f"You received a {rarity} {item_type}!",
            color=rarity_colors.get(rarity.lower(), EmbedColors.SAKURA_PINK)
        )
        
        embed.add_field(name="Type", value=item_type.title(), inline=True)
        embed.add_field(name="Rarity", value=rarity.title(), inline=True)
        
        return embed
    
    @staticmethod
    def event_announcement(
        event_name: str,
        event_type: str,
        description: str,
        requirements: Optional[List[str]] = None,
        rewards: Optional[List[str]] = None
    ) -> discord.Embed:
        """Create an event announcement embed"""
        embed = SakuraEmbed.create_base(
            title=f"🎊 {event_name}",
            description=description,
            color=EmbedColors.STORM_PURPLE
        )
        
        embed.add_field(name="📋 Event Type", value=event_type, inline=False)
        
        if requirements:
            req_text = "\n".join([f"• {req}" for req in requirements])
            embed.add_field(name="📌 Requirements", value=req_text, inline=False)
        
        if rewards:
            reward_text = "\n".join([f"• {reward}" for reward in rewards])
            embed.add_field(name="🎁 Rewards", value=reward_text, inline=False)
        
        embed.set_footer(text="Gather your friends and join the celebration!")
        
        return embed
    
    @staticmethod
    def error(message: str) -> discord.Embed:
        """Create an error embed"""
        embed = SakuraEmbed.create_base(
            title="❌ Error",
            description=message,
            color=EmbedColors.ERROR
        )
        return embed
    
    @staticmethod
    def success(message: str) -> discord.Embed:
        """Create a success embed"""
        embed = SakuraEmbed.create_base(
            title="✅ Success",
            description=message,
            color=EmbedColors.SUCCESS
        )
        return embed
    
    @staticmethod
    def info(title: str, message: str) -> discord.Embed:
        """Create an info embed"""
        embed = SakuraEmbed.create_base(
            title=f"ℹ️ {title}",
            description=message,
            color=EmbedColors.MOONLIGHT
        )
        return embed
