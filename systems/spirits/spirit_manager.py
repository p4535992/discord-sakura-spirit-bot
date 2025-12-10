"""
Spirit lifecycle and management system
"""
import logging
import random
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Spirit, UserSpirit, SpiritRoaming
from systems.spirits.spirit_ai import SpiritAI

logger = logging.getLogger(__name__)


class SpiritManager:
    """Manage spirit entities and their lifecycle"""
    
    @staticmethod
    async def create_spirit(
        session: AsyncSession,
        rarity: str,
        faction: str,
        element: Optional[str] = None
    ) -> Spirit:
        """Create a new spirit with AI-generated personality"""
        
        # Generate personality using AI
        personality_data = await SpiritAI.generate_spirit_personality(rarity, faction, element)
        
        spirit = Spirit(
            name=personality_data.get("name", "Unknown Spirit"),
            rarity=rarity,
            faction=faction,
            base_power=SpiritManager._calculate_base_power(rarity),
            element=element or "neutral",
            personality=personality_data.get("personality", "mysterious"),
            appearance_description=personality_data.get("appearance_description"),
            color_scheme=personality_data.get("color_scheme"),
            behavior_profile={
                "interaction_style": personality_data.get("personality"),
                "preferred_weather": SpiritManager._get_preferred_weather(faction),
                "activity_level": random.uniform(0.5, 1.0)
            },
            abilities=personality_data.get("abilities", [])
        )
        
        session.add(spirit)
        await session.commit()
        await session.refresh(spirit)
        
        logger.info(f"Created new spirit: {spirit.name} ({rarity}, {faction})")
        
        return spirit
    
    @staticmethod
    def _calculate_base_power(rarity: str) -> int:
        """Calculate base power based on rarity"""
        power_map = {
            "common": random.randint(10, 20),
            "uncommon": random.randint(20, 35),
            "rare": random.randint(35, 55),
            "epic": random.randint(55, 80),
            "legendary": random.randint(80, 100)
        }
        return power_map.get(rarity, 10)
    
    @staticmethod
    def _get_preferred_weather(faction: str) -> List[str]:
        """Get preferred weather types for faction"""
        weather_preferences = {
            "Blossoms": ["Petal Storm", "Gentle Breeze", "Golden Hour"],
            "Moonborn": ["Lunar Bloom", "Eclipse", "Twilight Veil"],
            "Stormkin": ["Thunder Blossom", "Chaos Wind", "Mistfall"]
        }
        return weather_preferences.get(faction, ["Gentle Breeze"])
    
    @staticmethod
    async def get_random_spirit(session: AsyncSession, rarity: Optional[str] = None) -> Optional[Spirit]:
        """Get a random spirit, optionally filtered by rarity"""
        query = select(Spirit)
        
        if rarity:
            query = query.where(Spirit.rarity == rarity)
        
        result = await session.execute(query)
        spirits = result.scalars().all()
        
        if not spirits:
            return None
        
        return random.choice(spirits)
    
    @staticmethod
    async def assign_spirit_to_user(
        session: AsyncSession,
        user_id: int,
        spirit_id: int,
        custom_name: Optional[str] = None
    ) -> UserSpirit:
        """Assign a spirit companion to a user"""
        
        user_spirit = UserSpirit(
            user_id=user_id,
            spirit_id=spirit_id,
            custom_name=custom_name,
            mood="Curious",
            power_level=1,
            evolution_stage=1,
            bond_level=0
        )
        
        session.add(user_spirit)
        await session.commit()
        await session.refresh(user_spirit)
        
        logger.info(f"Assigned spirit {spirit_id} to user {user_id}")
        
        return user_spirit
    
    @staticmethod
    async def get_user_spirit(session: AsyncSession, user_id: int) -> Optional[UserSpirit]:
        """Get user's companion spirit"""
        result = await session.execute(
            select(UserSpirit)
            .where(UserSpirit.user_id == user_id)
            .order_by(UserSpirit.acquired_at.desc())
        )
        return result.scalars().first()
    
    @staticmethod
    async def interact_with_spirit(
        session: AsyncSession,
        user_spirit: UserSpirit,
        interaction_type: str
    ) -> Dict[str, Any]:
        """Handle user interaction with their spirit"""
        
        # Update last interaction time
        user_spirit.last_interaction = datetime.utcnow()
        
        # Increase bond level
        bond_gain = random.randint(1, 5)
        user_spirit.bond_level += bond_gain
        
        # Check for evolution
        evolved = False
        if user_spirit.bond_level >= user_spirit.evolution_stage * 100:
            user_spirit.evolution_stage += 1
            user_spirit.power_level += 10
            evolved = True
        
        await session.commit()
        
        return {
            "bond_gained": bond_gain,
            "new_bond_level": user_spirit.bond_level,
            "evolved": evolved,
            "new_evolution_stage": user_spirit.evolution_stage if evolved else None
        }
    
    @staticmethod
    async def update_spirit_mood(
        session: AsyncSession,
        user_spirit: UserSpirit,
        weather: str,
        server_harmony: float
    ) -> str:
        """Update spirit's mood based on context"""
        
        # Get spirit data
        result = await session.execute(
            select(Spirit).where(Spirit.id == user_spirit.spirit_id)
        )
        spirit = result.scalar_one()
        
        # Calculate interaction count (simplified)
        interaction_count = user_spirit.bond_level // 10
        
        # Generate new mood using AI
        new_mood = await SpiritAI.generate_spirit_mood(
            personality=spirit.personality,
            recent_interactions=interaction_count,
            weather=weather,
            server_harmony=server_harmony
        )
        
        user_spirit.mood = new_mood
        await session.commit()
        
        return new_mood
    
    @staticmethod
    async def spawn_roaming_spirit(
        session: AsyncSession,
        server_discord_id: int,
        channel_id: int,
        weather: str
    ) -> Optional[SpiritRoaming]:
        """Spawn a spirit to roam in a channel"""
        
        # Get a random spirit
        spirit = await SpiritManager.get_random_spirit(session)
        
        if not spirit:
            logger.warning("No spirits available for roaming")
            return None
        
        # Create roaming instance
        roaming = SpiritRoaming(
            spirit_id=spirit.id,
            server_discord_id=server_discord_id,
            channel_id=channel_id,
            current_mood=random.choice(["Curious", "Playful", "Mysterious", "Peaceful"]),
            spawn_reason="scheduled_roam",
            can_interact=True,
            interaction_count=0
        )
        
        session.add(roaming)
        await session.commit()
        await session.refresh(roaming)
        
        logger.info(f"Spirit {spirit.name} spawned in channel {channel_id}")
        
        return roaming
    
    @staticmethod
    async def get_active_roaming_spirits(
        session: AsyncSession,
        server_discord_id: int
    ) -> List[SpiritRoaming]:
        """Get all active roaming spirits in a server"""
        result = await session.execute(
            select(SpiritRoaming)
            .where(SpiritRoaming.server_discord_id == server_discord_id)
            .where(SpiritRoaming.despawn_at.is_(None))
        )
        return result.scalars().all()
    
    @staticmethod
    async def despawn_spirit(session: AsyncSession, roaming_spirit: SpiritRoaming):
        """Despawn a roaming spirit"""
        roaming_spirit.despawn_at = datetime.utcnow()
        roaming_spirit.can_interact = False
        await session.commit()
        
        logger.info(f"Spirit {roaming_spirit.spirit_id} despawned from server {roaming_spirit.server_discord_id}")
    
    @staticmethod
    async def initialize_default_spirits(session: AsyncSession):
        """Initialize a set of default spirits for the bot"""
        
        default_spirits = [
            {"rarity": "common", "faction": "Blossoms", "element": "nature"},
            {"rarity": "common", "faction": "Moonborn", "element": "light"},
            {"rarity": "uncommon", "faction": "Stormkin", "element": "wind"},
            {"rarity": "rare", "faction": "Blossoms", "element": "nature"},
            {"rarity": "epic", "faction": "Moonborn", "element": "light"},
            {"rarity": "legendary", "faction": "Stormkin", "element": "lightning"},
        ]
        
        for spirit_data in default_spirits:
            # Check if similar spirit already exists
            result = await session.execute(
                select(Spirit)
                .where(Spirit.rarity == spirit_data["rarity"])
                .where(Spirit.faction == spirit_data["faction"])
            )
            existing = result.scalars().first()
            
            if not existing:
                await SpiritManager.create_spirit(
                    session,
                    rarity=spirit_data["rarity"],
                    faction=spirit_data["faction"],
                    element=spirit_data["element"]
                )
        
        logger.info("Default spirits initialized")
