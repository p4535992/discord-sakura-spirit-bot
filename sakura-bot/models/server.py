"""
Server-related database models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class Server(Base):
    """Server configuration and state"""
    __tablename__ = "servers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    
    # Server State
    harmony_score = Column(Float, default=50.0)  # 0-100 scale
    current_weather = Column(String(50), default="Gentle Breeze")
    weather_changed_at = Column(DateTime, default=datetime.utcnow)
    faction_dominance = Column(String(50), default="Blossoms")
    
    # Configuration
    config_json = Column(JSON, nullable=True)
    enabled_features = Column(JSON, default=dict)
    
    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    weather_history = relationship("WeatherHistory", back_populates="server", cascade="all, delete-orphan")
    faction_scores = relationship("FactionScore", back_populates="server", cascade="all, delete-orphan")
    world_events = relationship("WorldEvent", back_populates="server", cascade="all, delete-orphan")
    codex_entries = relationship("CodexEntry", back_populates="server", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Server(discord_id={self.discord_id}, name={self.name}, harmony={self.harmony_score})>"


class WeatherHistory(Base):
    """Track weather changes over time"""
    __tablename__ = "weather_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    
    weather_type = Column(String(50), nullable=False)
    triggered_by = Column(String(100), nullable=True)  # ritual, scheduled, manual
    trigger_user_id = Column(BigInteger, nullable=True)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # Weather effects during this period
    effects_json = Column(JSON, nullable=True)
    
    # Relationship
    server = relationship("Server", back_populates="weather_history")
    
    def __repr__(self):
        return f"<WeatherHistory(server_id={self.server_id}, weather={self.weather_type})>"


class FactionScore(Base):
    """Track faction dominance scores"""
    __tablename__ = "faction_scores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    
    faction_name = Column(String(50), nullable=False)
    score = Column(Float, default=0.0)
    member_count = Column(Integer, default=0)
    
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    server = relationship("Server", back_populates="faction_scores")
    
    def __repr__(self):
        return f"<FactionScore(server_id={self.server_id}, faction={self.faction_name}, score={self.score})>"


class Relationship(Base):
    """Track relationships between users"""
    __tablename__ = "relationships"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    user_id_1 = Column(BigInteger, nullable=False, index=True)
    user_id_2 = Column(BigInteger, nullable=False, index=True)
    
    # Relationship Metrics
    warmth_score = Column(Float, default=0.0)  # Positive interactions
    rivalry_score = Column(Float, default=0.0)  # Competitive interactions
    synergy_score = Column(Float, default=0.0)  # Cooperative success
    chaos_score = Column(Float, default=0.0)  # Unpredictable interactions
    
    # Interaction Counts
    total_interactions = Column(Integer, default=0)
    last_interaction = Column(DateTime, default=datetime.utcnow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Relationship(users={self.user_id_1}-{self.user_id_2}, warmth={self.warmth_score})>"
