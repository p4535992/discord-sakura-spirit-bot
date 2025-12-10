"""
World and event-related database models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Float, JSON, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from .base import Base


class WorldEvent(Base):
    """Server-wide events and activities"""
    __tablename__ = "world_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False)  # ritual, boss, festival, etc.
    event_name = Column(String(255), nullable=False)
    event_description = Column(Text, nullable=True)
    
    # Event State
    status = Column(String(50), default="active")  # active, completed, failed
    participants = Column(JSON, default=list)  # List of user discord IDs
    outcome = Column(JSON, nullable=True)  # Event results
    
    # Rewards
    rewards_distributed = Column(Boolean, default=False)
    rewards_json = Column(JSON, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # Relationship
    server = relationship("Server", back_populates="world_events")
    
    def __repr__(self):
        return f"<WorldEvent(server_id={self.server_id}, type={self.event_type}, status={self.status})>"


class CodexEntry(Base):
    """Lore system entries"""
    __tablename__ = "codex_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # legend, discovery, timeline, spirit, etc.
    
    # Unlock Conditions
    unlocked_by = Column(String(100), nullable=True)  # event, ritual, exploration, etc.
    unlock_trigger = Column(String(255), nullable=True)
    
    # Metadata
    related_users = Column(JSON, default=list)  # User IDs involved
    related_spirits = Column(JSON, default=list)  # Spirit IDs involved
    tags = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    server = relationship("Server", back_populates="codex_entries")
    
    def __repr__(self):
        return f"<CodexEntry(server_id={self.server_id}, title={self.title})>"


class ParkZone(Base):
    """Sakura Park zone definitions"""
    __tablename__ = "park_zones"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=False)
    
    # Zone Properties
    zone_type = Column(String(50), nullable=False)  # shrine, garden, shop, fishing, etc.
    required_level = Column(Integer, default=1)
    connected_zones = Column(JSON, default=list)  # List of zone IDs
    
    # Features
    has_npc = Column(Boolean, default=False)
    has_shop = Column(Boolean, default=False)
    has_minigame = Column(Boolean, default=False)
    
    # Atmosphere
    ambiance = Column(String(255), nullable=True)
    weather_effects = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ParkZone(name={self.name}, type={self.zone_type})>"


class NPC(Base):
    """Non-player characters in Sakura Park"""
    __tablename__ = "npcs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    zone_id = Column(Integer, ForeignKey("park_zones.id"), nullable=False)
    
    # NPC Properties
    personality = Column(String(50), nullable=False)
    appearance = Column(String(500), nullable=True)
    dialogue_style = Column(String(100), nullable=True)
    
    # Behavior
    schedule = Column(JSON, nullable=True)  # Time-based location changes
    interaction_types = Column(JSON, default=list)  # quest, shop, dialogue, etc.
    
    # Relationships with players
    relationship_tracking = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<NPC(name={self.name}, zone_id={self.zone_id})>"


class UserZoneProgress(Base):
    """Track user exploration progress"""
    __tablename__ = "user_zone_progress"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_discord_id = Column(BigInteger, nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey("park_zones.id"), nullable=False)
    
    # Progress
    visited = Column(Boolean, default=False)
    visit_count = Column(Integer, default=0)
    first_visit = Column(DateTime, nullable=True)
    last_visit = Column(DateTime, nullable=True)
    
    # Discoveries
    secrets_found = Column(JSON, default=list)
    items_collected = Column(JSON, default=list)
    
    def __repr__(self):
        return f"<UserZoneProgress(user={self.user_discord_id}, zone={self.zone_id})>"


class Shop(Base):
    """Shop inventory and transactions"""
    __tablename__ = "shops"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey("park_zones.id"), nullable=False)
    name = Column(String(100), nullable=False)
    
    # Shop Properties
    shop_type = Column(String(50), nullable=False)  # general, cosmetic, spirit, etc.
    inventory = Column(JSON, default=list)  # List of item IDs and stock
    
    # Refresh
    refresh_interval = Column(Integer, default=86400)  # seconds (default: daily)
    last_refresh = Column(DateTime, default=datetime.utcnow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Shop(name={self.name}, zone_id={self.zone_id})>"


class Quest(Base):
    """Quest system"""
    __tablename__ = "quests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Quest Properties
    quest_type = Column(String(50), nullable=False)  # daily, weekly, story, special
    difficulty = Column(String(50), default="normal")
    
    # Requirements
    required_level = Column(Integer, default=1)
    prerequisites = Column(JSON, default=list)  # Quest IDs that must be completed first
    
    # Objectives
    objectives = Column(JSON, nullable=False)  # List of objectives
    
    # Rewards
    rewards = Column(JSON, nullable=False)
    
    # Availability
    repeatable = Column(Boolean, default=False)
    time_limited = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Quest(title={self.title}, type={self.quest_type})>"


class UserQuest(Base):
    """Track user quest progress"""
    __tablename__ = "user_quests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_discord_id = Column(BigInteger, nullable=False, index=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    
    # Progress
    status = Column(String(50), default="active")  # active, completed, abandoned
    progress = Column(JSON, default=dict)  # Objective completion tracking
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<UserQuest(user={self.user_discord_id}, quest={self.quest_id}, status={self.status})>"
