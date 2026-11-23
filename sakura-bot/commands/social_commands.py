"""
Social interaction commands
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

from utils.embed_builder import SakuraEmbed
from core.database import get_db_session
from core.services import UserService

logger = logging.getLogger(__name__)


class SocialCommands(commands.Cog):
    """Social interaction commands"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="sakura-send-gift", description="Send a gift to another user")
    @app_commands.describe(user="The user to send a gift to", gift_type="Type of gift to send")
    async def send_gift(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        gift_type: str = "flower"
    ):
        """Send a gift to another user"""
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't send a gift to yourself!")
            return
        
        if user.bot:
            await interaction.response.send_message("❌ You can't send gifts to bots!")
            return
        
        async with get_db_session() as session:
            sender = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            recipient = await UserService.get_or_create_user(
                session,
                user.id,
                user.name
            )
            
            # Cost for sending gift
            gift_cost = 50
            
            if not await UserService.spend_currency(session, sender, gift_cost):
                embed = SakuraEmbed.error(
                    f"You need {gift_cost} currency to send a gift! (You have {sender.currency})"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Give currency to recipient
            await UserService.add_currency(session, recipient, 30)
            
            # Update stats
            from sqlalchemy import select
            from models import UserStats
            
            result = await session.execute(
                select(UserStats).where(UserStats.user_id == sender.id)
            )
            sender_stats = result.scalar_one_or_none()
            if sender_stats:
                sender_stats.gifts_sent += 1
            
            result = await session.execute(
                select(UserStats).where(UserStats.user_id == recipient.id)
            )
            recipient_stats = result.scalar_one_or_none()
            if recipient_stats:
                recipient_stats.gifts_received += 1
            
            await session.commit()
            
            # Create gift embed
            gift_emojis = {
                "flower": "🌸",
                "star": "⭐",
                "heart": "💖",
                "moon": "🌙",
                "crystal": "💎"
            }
            
            emoji = gift_emojis.get(gift_type, "🎁")
            
            embed = SakuraEmbed.create_base(
                title=f"{emoji} Gift Sent!",
                description=f"**{interaction.user.name}** sent a {gift_type} to **{user.name}**!",
                color=0xFFB7C5
            )
            
            embed.add_field(name="💰 Cost", value=f"{gift_cost} currency", inline=True)
            embed.add_field(name="🎁 Recipient Received", value="30 currency", inline=True)
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-daily-dream", description="View your daily dream")
    async def daily_dream(self, interaction: discord.Interaction):
        """Display user's daily dream"""
        await interaction.response.defer()
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Check for existing dream today
            from sqlalchemy import select
            from models import DailyDream
            
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            result = await session.execute(
                select(DailyDream)
                .where(DailyDream.user_id == user.id)
                .where(DailyDream.generated_at >= today_start)
                .order_by(DailyDream.generated_at.desc())
            )
            dream = result.scalars().first()
            
            if not dream:
                # Generate new dream
                from systems.spirits.spirit_ai import SpiritAI
                
                dream_content = await self._generate_dream_content(
                    user.emotional_state,
                    user.level
                )
                
                dream = DailyDream(
                    user_id=user.id,
                    dream_content=dream_content["content"],
                    dream_type=dream_content["type"],
                    effects=dream_content["effects"],
                    generated_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=1),
                    viewed=False
                )
                
                session.add(dream)
                await session.commit()
            
            # Mark as viewed
            if not dream.viewed:
                dream.viewed = True
                await session.commit()
            
            # Create dream embed
            embed = SakuraEmbed.create_base(
                title="🌙 Your Daily Dream",
                description=dream.dream_content,
                color=0xE6E6FA
            )
            
            embed.add_field(name="✨ Dream Type", value=dream.dream_type.title(), inline=True)
            
            if dream.effects:
                effects_text = "\n".join([f"• {k}: {v}" for k, v in dream.effects.items()])
                embed.add_field(name="🎁 Effects", value=effects_text, inline=False)
            
            # Calculate time until next dream
            time_until_next = dream.expires_at - datetime.utcnow()
            hours = int(time_until_next.total_seconds() // 3600)
            
            embed.set_footer(text=f"Next dream in {hours} hours")
            
            await interaction.followup.send(embed=embed)
    
    async def _generate_dream_content(self, emotional_state: str, level: int) -> dict:
        """Generate dream content based on user state"""
        import random
        
        dream_types = ["prophetic", "empowering", "mysterious", "peaceful", "chaotic"]
        dream_type = random.choice(dream_types)
        
        dreams = {
            "prophetic": [
                "You see cherry blossoms falling in reverse, rising towards the sky. A voice whispers of changes to come.",
                "In your dream, spirits gather around you, their eyes glowing with ancient knowledge.",
                "You walk through a garden where time flows differently, seeing both past and future."
            ],
            "empowering": [
                "You feel power surge through you as petals swirl around your form, granting you strength.",
                "A legendary spirit appears and bestows upon you a fragment of their essence.",
                "You stand atop a mountain of blossoms, feeling invincible and full of determination."
            ],
            "mysterious": [
                "Strange symbols appear in the sky, their meaning just beyond your understanding.",
                "You hear a melody that seems to come from everywhere and nowhere at once.",
                "A door appears before you, but when you reach for it, it fades like mist."
            ],
            "peaceful": [
                "You rest beneath a cherry tree, feeling completely at peace as petals fall gently around you.",
                "Warm light bathes you as you float among clouds made of soft pink blossoms.",
                "You find yourself in a tranquil garden where all worries melt away."
            ],
            "chaotic": [
                "Reality shifts and warps around you as multiple versions of yourself appear and disappear.",
                "You're caught in a storm of petals that carries you through impossible spaces.",
                "Time loops and repeats, each cycle slightly different from the last."
            ]
        }
        
        content = random.choice(dreams.get(dream_type, dreams["peaceful"]))
        
        # Generate effects based on type
        effects = {}
        if dream_type == "empowering":
            effects["xp_boost"] = "10%"
            effects["duration"] = "24 hours"
        elif dream_type == "prophetic":
            effects["gacha_luck"] = "+5%"
        elif dream_type == "peaceful":
            effects["harmony_contribution"] = "+2"
        
        return {
            "content": content,
            "type": dream_type,
            "effects": effects
        }
    
    @app_commands.command(name="sakura-relationships", description="View your relationships with other users")
    async def relationships(self, interaction: discord.Interaction):
        """Display user relationships"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server!")
            return
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Get relationships
            from sqlalchemy import select, or_
            from models import Relationship
            
            result = await session.execute(
                select(Relationship)
                .where(
                    or_(
                        Relationship.user_id_1 == interaction.user.id,
                        Relationship.user_id_2 == interaction.user.id
                    )
                )
                .where(Relationship.server_id == interaction.guild.id)
                .order_by(Relationship.warmth_score.desc())
                .limit(5)
            )
            relationships = result.scalars().all()
            
            if not relationships:
                embed = SakuraEmbed.info(
                    "No Relationships",
                    "You haven't formed any relationships yet. Interact with others to build connections!"
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = SakuraEmbed.create_base(
                title="💫 Your Relationships",
                description="Your connections with other users in this server",
                color=0xFFB7C5
            )
            
            for rel in relationships:
                # Determine other user
                other_user_id = rel.user_id_2 if rel.user_id_1 == interaction.user.id else rel.user_id_1
                
                try:
                    other_user = await self.bot.fetch_user(other_user_id)
                    other_name = other_user.name
                except:
                    other_name = f"User {other_user_id}"
                
                # Determine relationship type
                scores = {
                    "Warmth": rel.warmth_score,
                    "Rivalry": rel.rivalry_score,
                    "Synergy": rel.synergy_score,
                    "Chaos": rel.chaos_score
                }
                
                dominant_type = max(scores, key=scores.get)
                dominant_score = scores[dominant_type]
                
                embed.add_field(
                    name=f"💖 {other_name}",
                    value=f"{dominant_type}: {dominant_score:.1f}\nInteractions: {rel.total_interactions}",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(SocialCommands(bot))
    logger.info("SocialCommands cog loaded")
