"""
Spirit-related database models
"""
from datetime import datetime
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from .base import Base


class Spirit(Base):
    """Spirit entity definition"""
    __tablename__ = "spirits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    rarity = Column(String(50), nullable=False)  # common, uncommon, rare, epic, legendary
    faction = Column(String(50), nullable=False)  # Blossoms, Moonborn, Stormkin
    
    # Spirit Attributes
    base_power = Column(Integer, default=10)
    element = Column(String(50), nullable=True)  # fire, water, earth, air, light, dark
    personality = Column(String(50), nullable=False)  # cheerful, mysterious, stoic, playful, etc.
    
    # Appearance
    appearance_description = Column(String(500), nullable=True)
    color_scheme = Column(String(100), nullable=True)
    
    # Behavior Profile
    behavior_profile = Column(JSON, nullable=True)  # AI behavior parameters
    
    # Abilities
    abilities = Column(JSON, nullable=True)  # List of special abilities
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Spirit(name={self.name}, rarity={self.rarity}, faction={self.faction})>"


class SpiritInteraction(Base):
    """Track spirit interactions with users"""
    __tablename__ = "spirit_interactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    spirit_id = Column(Integer, ForeignKey("spirits.id"), nullable=False, index=True)
    user_discord_id = Column(BigInteger, nullable=False, index=True)
    server_discord_id = Column(BigInteger, nullable=False, index=True)
    
    interaction_type = Column(String(50), nullable=False)  # greeting, quest, gift, battle, etc.
    interaction_content = Column(String(1000), nullable=True)
    
    # Context
    weather_at_time = Column(String(50), nullable=True)
    user_emotional_state = Column(String(50), nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SpiritInteraction(spirit_id={self.spirit_id}, type={self.interaction_type})>"


class SpiritRoaming(Base):
    """Track active roaming spirits in servers"""
    __tablename__ = "spirit_roaming"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    spirit_id = Column(Integer, ForeignKey("spirits.id"), nullable=False)
    server_discord_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=True)
    
    # Roaming State
    current_mood = Column(String(50), default="Curious")
    current_activity = Column(String(100), nullable=True)
    spawn_reason = Column(String(100), nullable=True)
    
    # Interaction State
    can_interact = Column(Boolean, default=True)
    interaction_count = Column(Integer, default=0)
    
    spawned_at = Column(DateTime, default=datetime.utcnow)
    despawn_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<SpiritRoaming(spirit_id={self.spirit_id}, server={self.server_discord_id})>"
