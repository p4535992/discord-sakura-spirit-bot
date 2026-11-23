"""
Gacha and cosmetics commands
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
import random

from utils.embed_builder import SakuraEmbed
from core.database import get_db_session
from core.services import UserService
from core.config import settings

logger = logging.getLogger(__name__)


class GachaCommands(commands.Cog):
    """Commands for gacha and cosmetics"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="sakura-gacha-pull",
                          description="Pull from the gacha for a chance to win spirits or items")
    async def gacha_pull(self, interaction: discord.Interaction):
        """Perform a gacha pull"""
        await interaction.response.defer()
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Check if user has enough currency
            if not await UserService.spend_currency(session, user, settings.gacha_cost):
                embed = SakuraEmbed.error(
                    f"You need {settings.gacha_cost} currency to pull! (You have {user.currency})"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Perform gacha roll
            pull_result = self._perform_gacha_roll()
            
            # Add item to inventory
            from models import UserInventory
            
            inventory_item = UserInventory(
                user_id=user.id,
                item_type=pull_result["type"],
                item_id=pull_result["id"],
                item_name=pull_result["name"],
                item_rarity=pull_result["rarity"],
                quantity=1
            )
            session.add(inventory_item)
            await session.commit()
            
            # Create result embed
            embed = SakuraEmbed.gacha_result(
                item_name=pull_result["name"],
                item_type=pull_result["type"],
                rarity=pull_result["rarity"],
                description=f"You spent {settings.gacha_cost} currency and received..."
            )
            
            await interaction.followup.send(embed=embed)
    
    def _perform_gacha_roll(self) -> dict:
        """Perform a gacha roll and return the result"""
        
        # Determine rarity
        rarity_rates = settings.gacha_rarity_rates
        rarities = list(rarity_rates.keys())
        weights = list(rarity_rates.values())
        
        chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]
        
        # Determine item type
        item_type = random.choice(['spirit', 'cosmetic', 'item', 'badge'])
        
        # Generate item based on rarity and type
        if item_type == 'spirit':
            # In a real implementation, this would pull from the spirits table
            spirit_names = {
                "common": ["Kodama", "Mokumoku"],
                "uncommon": ["Kitsune", "Tanuki"],
                "rare": ["Nekomata", "Raiju"],
                "epic": ["Kirin", "Hou-ou"],
                "legendary": ["Ryujin", "Amaterasu"]
            }
            name = random.choice(spirit_names[chosen_rarity])
            item_id = name.lower()
        elif item_type == 'cosmetic':
            cosmetic_types = ["Aura", "Role Color", "Profile Background"]
            name = f"{chosen_rarity.title()} {random.choice(cosmetic_types)}"
            item_id = name.lower().replace(" ", "_")
        elif item_type == 'item':
            item_names = ["XP Potion", "Gacha Ticket", "Spirit Charm"]
            name = f"{chosen_rarity.title()} {random.choice(item_names)}"
            item_id = name.lower().replace(" ", "_")
        else:  # badge
            badge_themes = ["Sakura", "Moon", "Storm", "Sun"]
            name = f"{chosen_rarity.title()} {random.choice(badge_themes)} Badge"
            item_id = name.lower().replace(" ", "_")
        
        return {
            "name": name,
            "type": item_type,
            "rarity": chosen_rarity,
            "id": item_id
        }

async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(GachaCommands(bot))
    logger.info("GachaCommands cog loaded")
