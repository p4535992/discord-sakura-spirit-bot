"""
World exploration and Sakura Park commands
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
import random

from utils.embed_builder import SakuraEmbed
from core.database import get_db_session
from core.services import UserService

logger = logging.getLogger(__name__)


class WorldCommands(commands.Cog):
    """Commands for world exploration"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.zones = self._initialize_zones()
    
    def _initialize_zones(self) -> dict:
        """Initialize Sakura Park zones"""
        return {
            "entrance": {
                "name": "🌸 Park Entrance",
                "description": "A grand torii gate marks the entrance to Sakura Park, petals swirling in the breeze.",
                "connections": ["garden", "shrine"],
                "features": ["Welcome NPC"]
            },
            "garden": {
                "name": "🌺 Cherry Blossom Garden",
                "description": "Endless rows of cherry trees create a pink canopy overhead.",
                "connections": ["entrance", "pond", "shop"],
                "features": ["Collectibles", "Photo Spot"]
            },
            "pond": {
                "name": "🎣 Koi Pond",
                "description": "A serene pond filled with colorful koi fish swimming beneath lily pads.",
                "connections": ["garden", "teahouse"],
                "features": ["Fishing Mini-game", "Meditation Spot"]
            },
            "shrine": {
                "name": "⛩️ Sacred Shrine",
                "description": "An ancient shrine dedicated to the spirits of the Sakura realm.",
                "connections": ["entrance", "forest"],
                "features": ["Prayer System", "Spirit Encounters"]
            },
            "shop": {
                "name": "🏪 Spirit Shop",
                "description": "A mystical shop run by a friendly tanuki spirit.",
                "connections": ["garden"],
                "features": ["Shop", "NPC Trader"]
            },
            "teahouse": {
                "name": "🍵 Moonlit Teahouse",
                "description": "A cozy teahouse where spirits and visitors gather to rest.",
                "connections": ["pond", "forest"],
                "features": ["Rest Area", "NPC Conversations"]
            },
            "forest": {
                "name": "🌲 Mystic Forest",
                "description": "A dense forest where ancient spirits are said to dwell.",
                "connections": ["shrine", "teahouse", "summit"],
                "features": ["Rare Spirits", "Hidden Secrets"]
            },
            "summit": {
                "name": "⛰️ Blossom Summit",
                "description": "The highest point in the park, offering a breathtaking view.",
                "connections": ["forest"],
                "features": ["Panoramic View", "Rare Events"]
            }
        }
    
    @app_commands.command(name="sakura-explore", description="Explore Sakura Park")
    @app_commands.describe(destination="The zone you want to explore")
    async def explore(self, interaction: discord.Interaction, destination: str = "entrance"):
        """Explore a zone in Sakura Park"""
        destination = destination.lower()
        
        if destination not in self.zones:
            available_zones = ", ".join(self.zones.keys())
            await interaction.response.send_message(
                f"❌ Unknown zone! Available zones: {available_zones}"
            )
            return
        
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            zone_data = self.zones[destination]
            
            # Create exploration embed
            embed = SakuraEmbed.create_base(
                title=zone_data["name"],
                description=zone_data["description"],
                color=0xFFB7C5
            )
            
            # Add features
            features_text = "\n".join([f"• {feature}" for feature in zone_data["features"]])
            embed.add_field(name="✨ Features", value=features_text, inline=False)
            
            # Add connections
            connections_text = " → ".join([self.zones[conn]["name"] for conn in zone_data["connections"]])
            embed.add_field(name="🗺️ Connections", value=connections_text, inline=False)
            
            # Random discovery chance
            if random.random() < 0.2:  # 20% chance
                discoveries = [
                    "You found a hidden petal! (+10 currency)",
                    "A friendly spirit appeared and blessed you! (+5 XP)",
                    "You discovered a secret path!",
                    "A rare butterfly landed on your shoulder!",
                    "You found an ancient coin! (+25 currency)"
                ]
                discovery = random.choice(discoveries)
                embed.add_field(name="🎁 Discovery!", value=discovery, inline=False)
                
                # Give rewards
                if "currency" in discovery:
                    amount = int(discovery.split("+")[1].split()[0])
                    await UserService.add_currency(session, user, amount)
                elif "XP" in discovery:
                    amount = int(discovery.split("+")[1].split()[0])
                    leveled_up, new_level = await UserService.add_xp(session, user, amount)
            
            embed.set_footer(text="Use /explore <zone_name> to visit other areas")
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-shop", description="Visit the Spirit Shop")
    async def shop(self, interaction: discord.Interaction):
        """Display shop inventory"""
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            embed = SakuraEmbed.create_base(
                title="🏪 Spirit Shop",
                description="Welcome to the Spirit Shop! Browse our mystical wares.",
                color=0xFFB7C5
            )
            
            # Shop items
            items = [
                {"name": "Spirit Charm", "price": 100, "emoji": "🔮", "description": "Increases spirit bond gain"},
                {"name": "Lucky Petal", "price": 150, "emoji": "🍀", "description": "Boosts gacha luck temporarily"},
                {"name": "XP Potion", "price": 200, "emoji": "⚗️", "description": "Grants 50 XP instantly"},
                {"name": "Weather Charm", "price": 500, "emoji": "🌤️", "description": "Influence weather change"},
                {"name": "Rare Spirit Egg", "price": 1000, "emoji": "🥚", "description": "Hatch a rare spirit companion"}
            ]
            
            for item in items:
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"{item['description']}\n💰 Price: {item['price']}",
                    inline=True
                )
            
            embed.add_field(
                name="💰 Your Currency",
                value=str(user.currency),
                inline=False
            )
            
            embed.set_footer(text="Use /buy <item_name> to purchase items")
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-quests", description="View available quests")
    async def quests(self, interaction: discord.Interaction):
        """Display available quests"""
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            embed = SakuraEmbed.create_base(
                title="📜 Available Quests",
                description="Embark on adventures in the Sakura realm!",
                color=0xFFB7C5
            )
            
            # Sample quests
            quests = [
                {
                    "name": "🌸 Petal Collector",
                    "description": "Collect 10 cherry blossom petals",
                    "reward": "100 XP, 50 currency",
                    "difficulty": "Easy"
                },
                {
                    "name": "🎣 Master Angler",
                    "description": "Catch 5 rare koi fish",
                    "reward": "200 XP, Fishing Rod",
                    "difficulty": "Medium"
                },
                {
                    "name": "👻 Spirit Seeker",
                    "description": "Encounter 3 different spirit types",
                    "reward": "300 XP, Spirit Charm",
                    "difficulty": "Medium"
                },
                {
                    "name": "⛰️ Summit Climber",
                    "description": "Reach Blossom Summit",
                    "reward": "500 XP, Rare Badge",
                    "difficulty": "Hard"
                }
            ]
            
            for quest in quests:
                difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
                emoji = difficulty_emoji.get(quest["difficulty"], "⚪")
                
                embed.add_field(
                    name=f"{quest['name']} {emoji}",
                    value=f"{quest['description']}\n🎁 Reward: {quest['reward']}",
                    inline=False
                )
            
            embed.set_footer(text="Complete quests to earn rewards and unlock new content!")
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-map", description="View the Sakura Park map")
    async def map_command(self, interaction: discord.Interaction):
        """Display park map"""
        embed = SakuraEmbed.create_base(
            title="🗺️ Sakura Park Map",
            description="Explore the mystical Sakura Park and discover its secrets!",
            color=0xFFB7C5
        )
        
        map_text = """
```
        ⛰️ Summit
            |
        🌲 Forest ─── 🍵 Teahouse
            |              |
        ⛩️ Shrine      🎣 Pond
            |              |
        🌸 Entrance ─ 🌺 Garden ─ 🏪 Shop
```
        """
        
        embed.add_field(name="Park Layout", value=map_text, inline=False)
        
        zones_list = "\n".join([f"• {data['name']}" for data in self.zones.values()])
        embed.add_field(name="📍 All Zones", value=zones_list, inline=False)
        
        embed.set_footer(text="Use /explore <zone> to visit any location!")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sakura-inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        """Display user inventory"""
        async with get_db_session() as session:
            user = await UserService.get_or_create_user(
                session,
                interaction.user.id,
                interaction.user.name
            )
            
            # Get user inventory
            from sqlalchemy import select
            from models import UserInventory
            
            result = await session.execute(
                select(UserInventory)
                .where(UserInventory.user_id == user.id)
                .order_by(UserInventory.item_rarity.desc())
            )
            items = result.scalars().all()
            
            embed = SakuraEmbed.create_base(
                title=f"🎒 {interaction.user.name}'s Inventory",
                description=f"💰 Currency: {user.currency}",
                color=0xFFB7C5
            )
            
            if not items:
                embed.add_field(
                    name="Empty Inventory",
                    value="You don't have any items yet. Visit the shop or complete quests!",
                    inline=False
                )
            else:
                # Group by type
                by_type = {}
                for item in items:
                    if item.item_type not in by_type:
                        by_type[item.item_type] = []
                    by_type[item.item_type].append(item)
                
                for item_type, type_items in by_type.items():
                    items_text = "\n".join([
                        f"• {item.item_name} (x{item.quantity}) [{item.item_rarity}]"
                        for item in type_items[:5]  # Limit to 5 per type
                    ])
                    
                    embed.add_field(
                        name=f"📦 {item_type.title()}",
                        value=items_text,
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Load the cog"""
    await bot.add_cog(WorldCommands(bot))
    logger.info("WorldCommands cog loaded")
