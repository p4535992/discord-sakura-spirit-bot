"""
Gaming utility commands for LFG and team formation
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from utils.embed_builder import SakuraEmbed
from core.database import get_db_session
from core.services import UserService
from core.cache import cache

logger = logging.getLogger(__name__)


class GamingCommands(commands.Cog):
    """Gaming utility commands"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="lfg", description="Look for group to play a game")
    @app_commands.describe(
        game="The game you want to play",
        party_size="Number of players needed (including you)",
        message="Additional message for your LFG post"
    )
    async def lfg(
        self,
        interaction: discord.Interaction,
        game: str,
        party_size: int = 5,
        message: Optional[str] = None
    ):
        """Create an LFG (Looking for Group) post"""
        if party_size < 2 or party_size > 10:
            await interaction.response.send_message("❌ Party size must be between 2 and 10!")
            return
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Create LFG embed
            embed = SakuraEmbed.create_base(
                title=f"🎮 LFG: {game}",
                description=message or f"{interaction.user.name} is looking for a group!",
                color=0x7289DA
            )
            
            embed.add_field(name="👥 Party Size", value=f"1/{party_size}", inline=True)
            embed.add_field(name="🎯 Game", value=game, inline=True)
            embed.add_field(name="📍 Status", value="Open", inline=True)
            
            embed.add_field(
                name="✅ Joined Players",
                value=f"• {interaction.user.mention}",
                inline=False
            )
            
            embed.set_footer(text="React with ✅ to join this group!")
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
            # Get the message and add reaction
            message_obj = await interaction.original_response()
            await message_obj.add_reaction("✅")
            
            # Store LFG data in cache
            lfg_data = {
                "creator_id": interaction.user.id,
                "game": game,
                "party_size": party_size,
                "members": [interaction.user.id],
                "message_id": message_obj.id,
                "channel_id": interaction.channel.id
            }
            
            await cache.set_json(
                f"lfg:{interaction.guild.id}:{message_obj.id}",
                lfg_data,
                expire=3600  # 1 hour
            )
    
    @app_commands.command(name="ritual-buff", description="Perform a pre-game ritual for buffs")
    @app_commands.describe(ritual_type="Type of ritual to perform")
    async def ritual_buff(
        self,
        interaction: discord.Interaction,
        ritual_type: str = "victory"
    ):
        """Perform a pre-game ritual"""
        await interaction.response.defer()
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Check cooldown
            cooldown_key = f"ritual_cooldown:{interaction.user.id}"
            if await cache.exists(cooldown_key):
                embed = SakuraEmbed.error("You've already performed a ritual recently! Wait before trying again.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Ritual types and effects
            rituals = {
                "victory": {
                    "name": "Victory Ritual",
                    "description": "Channel the spirits of triumph",
                    "buffs": ["🎯 +10% Accuracy", "💪 +15% Confidence", "⚡ +5% Speed"],
                    "emoji": "🏆"
                },
                "focus": {
                    "name": "Focus Ritual",
                    "description": "Clear your mind and sharpen your senses",
                    "buffs": ["🧠 +20% Concentration", "👁️ +10% Awareness", "⏱️ +5% Reaction Time"],
                    "emoji": "🎯"
                },
                "teamwork": {
                    "name": "Teamwork Ritual",
                    "description": "Strengthen bonds with your allies",
                    "buffs": ["🤝 +15% Team Synergy", "💬 +10% Communication", "🛡️ +10% Support"],
                    "emoji": "👥"
                },
                "luck": {
                    "name": "Luck Ritual",
                    "description": "Invoke the favor of fortune",
                    "buffs": ["🍀 +25% Luck", "✨ +10% Critical Chance", "🎲 +5% RNG Favor"],
                    "emoji": "🍀"
                }
            }
            
            ritual_data = rituals.get(ritual_type, rituals["victory"])
            
            # Create ritual embed
            embed = SakuraEmbed.create_base(
                title=f"{ritual_data['emoji']} {ritual_data['name']}",
                description=f"*{interaction.user.name} {ritual_data['description']}*",
                color=0xFFD700
            )
            
            buffs_text = "\n".join(ritual_data["buffs"])
            embed.add_field(name="✨ Buffs Granted", value=buffs_text, inline=False)
            embed.add_field(name="⏰ Duration", value="Next 3 games or 2 hours", inline=True)
            
            embed.set_footer(text="May the spirits guide your gameplay! 🌸")
            
            await interaction.followup.send(embed=embed)
            
            # Set cooldown (30 minutes)
            await cache.set(cooldown_key, "1", expire=1800)
    
    @app_commands.command(name="game-stats", description="View your gaming statistics")
    async def game_stats(self, interaction: discord.Interaction):
        """Display user's gaming statistics"""
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Get user stats
            from sqlalchemy import select
            from models import UserStats
            
            result = await session.execute(
                select(UserStats).where(UserStats.user_id == user.id)
            )
            stats = result.scalar_one_or_none()
            
            if not stats:
                embed = SakuraEmbed.info("No Stats", "No gaming statistics available yet.")
                await interaction.response.send_message(embed=embed)
                return
            
            embed = SakuraEmbed.create_base(
                title=f"🎮 {interaction.user.name}'s Gaming Stats",
                description="Your gaming activity in the Sakura realm",
                color=0x7289DA
            )
            
            embed.add_field(name="🎯 Games Played", value=str(stats.games_played), inline=True)
            embed.add_field(name="👥 LFG Sessions", value=str(stats.lfg_sessions), inline=True)
            embed.add_field(name="🎊 Rituals Done", value=str(stats.rituals_participated), inline=True)
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Monitor voice channel activity for auto-LFG suggestions"""
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            # Check if there are other users in the channel
            if len(after.channel.members) >= 2:
                # Could send a suggestion to create an LFG post
                logger.info(f"{member.name} joined voice channel {after.channel.name} with {len(after.channel.members)} members")
        
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            logger.info(f"{member.name} left voice channel {before.channel.name}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle LFG reactions"""
        if payload.emoji.name != "✅":
            return
        
        if payload.member.bot:
            return
        
        # Check if this is an LFG message
        lfg_key = f"lfg:{payload.guild_id}:{payload.message_id}"
        lfg_data = await cache.get_json(lfg_key)
        
        if not lfg_data:
            return
        
        # Check if user is already in the group
        if payload.user_id in lfg_data["members"]:
            return
        
        # Check if group is full
        if len(lfg_data["members"]) >= lfg_data["party_size"]:
            return
        
        # Add user to group
        lfg_data["members"].append(payload.user_id)
        
        # Update cache
        await cache.set_json(lfg_key, lfg_data, expire=3600)
        
        # Update message
        try:
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            
            embed = message.embeds[0]
            
            # Update party size field
            embed.set_field_at(
                0,
                name="👥 Party Size",
                value=f"{len(lfg_data['members'])}/{lfg_data['party_size']}",
                inline=True
            )
            
            # Update members list
            members_text = "\n".join([f"• <@{uid}>" for uid in lfg_data["members"]])
            embed.set_field_at(
                3,
                name="✅ Joined Players",
                value=members_text,
                inline=False
            )
            
            # Check if full
            if len(lfg_data["members"]) >= lfg_data["party_size"]:
                embed.set_field_at(
                    2,
                    name="📍 Status",
                    value="Full!",
                    inline=True
                )
                embed.color = 0x43B581  # Green
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating LFG message: {e}")


async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(GamingCommands(bot))
    logger.info("GamingCommands cog loaded")
