"""
User-related database models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .base import Base


class User(Base):
    """Core user profile model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=False)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    currency = Column(Integer, default=0)
    emotional_state = Column(String(50), default="Blossoming")
    aura_type = Column(String(50), nullable=True)
    last_xp_gain = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    spirits = relationship("UserSpirit", back_populates="user", cascade="all, delete-orphan")
    inventory = relationship("UserInventory", back_populates="user", cascade="all, delete-orphan")
    stats = relationship("UserStats", back_populates="user", uselist=False, cascade="all, delete-orphan")
    emotional_history = relationship("EmotionalHistory", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(discord_id={self.discord_id}, username={self.username}, level={self.level})>"
    
    def add_xp(self, amount: int) -> bool:
        """Add XP and check for level up"""
        self.xp += amount
        xp_needed = self.xp_for_next_level()
        
        if self.xp >= xp_needed:
            self.level += 1
            self.xp -= xp_needed
            return True  # Level up occurred
        return False
    
    def xp_for_next_level(self) -> int:
        """Calculate XP needed for next level"""
        return int(100 * (self.level ** 1.5))


class UserStats(Base):
    """Extended user statistics"""
    __tablename__ = "user_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Activity Stats
    total_messages = Column(Integer, default=0)
    total_voice_time = Column(Integer, default=0)  # in seconds
    total_commands_used = Column(Integer, default=0)
    
    # Social Stats
    gifts_sent = Column(Integer, default=0)
    gifts_received = Column(Integer, default=0)
    rituals_participated = Column(Integer, default=0)
    
    # Gaming Stats
    games_played = Column(Integer, default=0)
    lfg_sessions = Column(Integer, default=0)
    
    # Gacha Stats
    total_pulls = Column(Integer, default=0)
    legendary_pulls = Column(Integer, default=0)
    
    # World Stats
    zones_explored = Column(Integer, default=0)
    npcs_met = Column(Integer, default=0)
    quests_completed = Column(Integer, default=0)
    
    # Relationship
    user = relationship("User", back_populates="stats")
    
    def __repr__(self):
        return f"<UserStats(user_id={self.user_id}, messages={self.total_messages})>"


class UserSpirit(Base):
    """User companion spirit model"""
    __tablename__ = "user_spirits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    spirit_id = Column(Integer, ForeignKey("spirits.id"), nullable=False)
    
    # Spirit State
    custom_name = Column(String(100), nullable=True)
    mood = Column(String(50), default="Neutral")
    power_level = Column(Integer, default=1)
    evolution_stage = Column(Integer, default=1)
    bond_level = Column(Integer, default=0)
    
    # Timestamps
    acquired_at = Column(DateTime, default=datetime.utcnow)
    last_interaction = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="spirits")
    spirit = relationship("Spirit")
    
    def __repr__(self):
        return f"<UserSpirit(user_id={self.user_id}, spirit_id={self.spirit_id}, power={self.power_level})>"


class UserInventory(Base):
    """User inventory for items and cosmetics"""
    __tablename__ = "user_inventory"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    item_type = Column(String(50), nullable=False)  # cosmetic, consumable, badge, etc.
    item_id = Column(String(100), nullable=False)
    item_name = Column(String(255), nullable=False)
    item_rarity = Column(String(50), nullable=False)
    quantity = Column(Integer, default=1)
    equipped = Column(Boolean, default=False)
    
    metadata = Column(JSON, nullable=True)  # Additional item data
    acquired_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="inventory")
    
    def __repr__(self):
        return f"<UserInventory(user_id={self.user_id}, item={self.item_name}, qty={self.quantity})>"


class EmotionalHistory(Base):
    """Track user emotional state changes over time"""
    __tablename__ = "emotional_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    emotional_state = Column(String(50), nullable=False)
    intensity = Column(Float, default=1.0)  # 0.0 to 1.0
    trigger_type = Column(String(100), nullable=True)  # What caused the change
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="emotional_history")
    
    def __repr__(self):
        return f"<EmotionalHistory(user_id={self.user_id}, state={self.emotional_state})>"


class DailyDream(Base):
    """Store daily generated dreams for users"""
    __tablename__ = "daily_dreams"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    dream_content = Column(String(1000), nullable=False)
    dream_type = Column(String(50), nullable=False)  # prophetic, empowering, mysterious, etc.
    effects = Column(JSON, nullable=True)  # Stat buffs or special effects
    
    generated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    viewed = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<DailyDream(user_id={self.user_id}, type={self.dream_type})>"
