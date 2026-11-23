"""
Spirit-related commands
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands

from utils.embed_builder import SakuraEmbed
from core.database import get_db_session
from core.services import UserService, ServerService
from systems.spirits.spirit_manager import SpiritManager
from systems.spirits.spirit_ai import SpiritAI

logger = logging.getLogger(__name__)


class SpiritCommands(commands.Cog):
    """Commands for interacting with spirits"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="sakura-my-spirit", description="View your companion spirit")
    async def my_spirit(self, interaction: discord.Interaction):
        """Display user's companion spirit"""
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            user_spirit = await SpiritManager.get_user_spirit(session, user.id)
            
            if not user_spirit:
                embed = SakuraEmbed.info(
                    "No Spirit Companion",
                    "You don't have a spirit companion yet! Use `/spirit-adopt` to get one."
                )
                await interaction.response.send_message(embed=embed)
                return
            
            # Get spirit details
            from sqlalchemy import select
            from models import Spirit
            
            result = await session.execute(
                select(Spirit).where(Spirit.id == user_spirit.spirit_id)
            )
            spirit = result.scalar_one()
            
            # Create spirit profile embed
            spirit_name = user_spirit.custom_name or spirit.name
            
            embed = SakuraEmbed.spirit_profile(
                spirit_name=spirit_name,
                rarity=spirit.rarity,
                faction=spirit.faction,
                power_level=user_spirit.power_level,
                mood=user_spirit.mood,
                description=spirit.appearance_description
            )
            
            embed.add_field(name="💖 Bond Level", value=str(user_spirit.bond_level), inline=True)
            embed.add_field(name="🌟 Evolution Stage", value=str(user_spirit.evolution_stage), inline=True)
            embed.add_field(name="⚡ Element", value=spirit.element.title(), inline=True)
            
            if spirit.abilities:
                abilities_text = ", ".join(spirit.abilities[:3])
                embed.add_field(name="✨ Abilities", value=abilities_text, inline=False)
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-spirit-interact", description="Interact with your spirit companion")
    @app_commands.describe(message="What do you want to say to your spirit?")
    async def spirit_interact(self, interaction: discord.Interaction, message: str):
        """Interact with user's spirit companion"""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!", ephemeral=True
            )
            return

        await interaction.response.defer()
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            user_spirit = await SpiritManager.get_user_spirit(session, user.id)
            
            if not user_spirit:
                embed = SakuraEmbed.error("You don't have a spirit companion yet!")
                await interaction.followup.send(embed=embed)
                return
            
            # Get spirit and server details
            from sqlalchemy import select
            from models import Spirit
            
            result = await session.execute(
                select(Spirit).where(Spirit.id == user_spirit.spirit_id)
            )
            spirit = result.scalar_one()
            
            server = await ServerService.get_or_create_server(
                session,
                interaction.guild.id,
                interaction.guild.name
            )
            
            # Generate AI response
            context = {
                "weather": server.current_weather,
                "user_emotional_state": user.emotional_state
            }
            
            spirit_name = user_spirit.custom_name or spirit.name
            
            response = await SpiritAI.generate_spirit_response(
                spirit_name=spirit_name,
                personality=spirit.personality,
                faction=spirit.faction,
                mood=user_spirit.mood,
                user_message=message,
                context=context
            )
            
            # Process interaction
            interaction_result = await SpiritManager.interact_with_spirit(
                session,
                user_spirit,
                "dialogue"
            )
            
            # Create response embed
            embed = SakuraEmbed.create_base(
                title=f"🌸 {spirit_name}",
                description=response,
                color=0xFFB7C5
            )
            
            bond_text = f"+{interaction_result['bond_gained']} bond"
            if interaction_result['evolved']:
                bond_text += f" | ⭐ Evolved to Stage {interaction_result['new_evolution_stage']}!"
            
            embed.set_footer(text=bond_text)
            
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="sakura-spirit-adopt", description="Adopt a spirit companion")
    async def spirit_adopt(self, interaction: discord.Interaction):
        """Allow user to adopt a spirit companion"""
        await interaction.response.defer()
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Check if user already has a spirit
            existing_spirit = await SpiritManager.get_user_spirit(session, user.id)
            
            if existing_spirit:
                embed = SakuraEmbed.error("You already have a spirit companion!")
                await interaction.followup.send(embed=embed)
                return
            
            # Get a random common spirit or create one
            spirit = await SpiritManager.get_random_spirit(session, rarity="common")
            
            if not spirit:
                # Create a new common spirit
                spirit = await SpiritManager.create_spirit(
                    session,
                    rarity="common",
                    faction="Blossoms",
                    element="nature"
                )
            
            # Assign spirit to user
            user_spirit = await SpiritManager.assign_spirit_to_user(
                session,
                user.id,
                spirit.id
            )
            
            # Create announcement embed
            embed = SakuraEmbed.create_base(
                title="🎉 Spirit Companion Adopted!",
                description=f"**{spirit.name}** has chosen to be your companion!",
                color=0xFFD700
            )
            
            embed.add_field(name="✨ Rarity", value=spirit.rarity.title(), inline=True)
            embed.add_field(name="⚔️ Faction", value=spirit.faction, inline=True)
            embed.add_field(name="💪 Power", value=str(user_spirit.power_level), inline=True)
            
            if spirit.appearance_description:
                embed.add_field(
                    name="📖 Description",
                    value=spirit.appearance_description,
                    inline=False
                )
            
            embed.set_footer(text="Use /my-spirit to view your companion anytime!")
            
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="sakura-spirit-info", description="Learn about spirits and factions")
    async def spirit_info(self, interaction: discord.Interaction):
        """Display information about spirits"""
        embed = SakuraEmbed.create_base(
            title="🌸 Spirit System Guide",
            description="Spirits are mystical entities that inhabit the Sakura realm",
            color=0xFFB7C5
        )
        
        embed.add_field(
            name="🌸 Blossoms Faction",
            value="Nature-aligned spirits of growth and harmony. Prefer gentle weather.",
            inline=False
        )
        
        embed.add_field(
            name="🌙 Moonborn Faction",
            value="Light and shadow spirits of mystery. Thrive under lunar conditions.",
            inline=False
        )
        
        embed.add_field(
            name="⚡ Stormkin Faction",
            value="Storm and chaos spirits of power. Energized by turbulent weather.",
            inline=False
        )
        
        embed.add_field(
            name="✨ Rarity Levels",
            value="Common → Uncommon → Rare → Epic → Legendary",
            inline=False
        )
        
        embed.add_field(
            name="💖 Bond System",
            value="Interact with your spirit to increase bond level and unlock evolution stages!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(SpiritCommands(bot))
    logger.info("SpiritCommands cog loaded")
