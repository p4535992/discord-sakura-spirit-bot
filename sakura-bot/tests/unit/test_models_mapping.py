"""ORM mapping regressions for the declarative models."""
from sqlalchemy import BigInteger, Integer

from models.base import Base
from models.server import Relationship, Server, WeatherHistory
from models.spirit import SpiritInteraction, SpiritRoaming
from models.user import User, UserInventory, UserStats
from models.world import UserQuest, UserZoneProgress

EXPECTED_TABLES = {
    "codex_entries",
    "daily_dreams",
    "emotional_history",
    "faction_scores",
    "npcs",
    "park_zones",
    "quests",
    "relationships",
    "servers",
    "shops",
    "spirit_interactions",
    "spirit_roaming",
    "spirits",
    "user_inventory",
    "user_quests",
    "user_spirits",
    "user_stats",
    "user_zone_progress",
    "users",
    "weather_history",
    "world_events",
}


def test_every_model_is_registered_on_the_metadata():
    """``create_all`` only creates tables that were imported before it runs."""
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_user_inventory_metadata_attribute_maps_to_metadata_column():
    """``metadata`` is reserved by the declarative API, the column name is not."""
    column_names = {column.name for column in UserInventory.__table__.columns}
    assert "metadata" in column_names
    assert "item_metadata" not in column_names


def test_user_inventory_accepts_item_metadata_payload():
    inventory = UserInventory(
        user_id=1,
        item_id="petal-charm",
        item_name="Petal Charm",
        item_type="charm",
        item_rarity="rare",
    )
    inventory.item_metadata = {"bonus": 5}
    assert inventory.item_metadata == {"bonus": 5}


# Discord snowflakes exceed 2**31-1, so PostgreSQL INTEGER (32 bit) cannot hold
# them. Every external Discord identifier must be mapped to BIGINT.
DISCORD_SNOWFLAKE_COLUMNS = (
    (User, "discord_id"),
    (Server, "discord_id"),
    (WeatherHistory, "trigger_user_id"),
    (Relationship, "user_id_1"),
    (Relationship, "user_id_2"),
    (SpiritInteraction, "user_discord_id"),
    (SpiritInteraction, "server_discord_id"),
    (SpiritRoaming, "server_discord_id"),
    (SpiritRoaming, "channel_id"),
    (UserZoneProgress, "user_discord_id"),
    (UserQuest, "user_discord_id"),
)

# Internal primary/foreign keys are not Discord identifiers and stay INTEGER.
INTERNAL_ID_COLUMNS = (
    (UserStats, "user_id"),
    (WeatherHistory, "server_id"),
    (Relationship, "server_id"),
    (SpiritInteraction, "spirit_id"),
    (SpiritRoaming, "spirit_id"),
    (UserZoneProgress, "zone_id"),
    (UserQuest, "quest_id"),
)


def test_discord_snowflake_columns_use_bigint():
    for model, name in DISCORD_SNOWFLAKE_COLUMNS:
        column = model.__table__.columns[name]
        assert isinstance(column.type, BigInteger), f"{model.__tablename__}.{name}"


def test_internal_relational_columns_stay_integer():
    for model, name in INTERNAL_ID_COLUMNS:
        column = model.__table__.columns[name]
        assert isinstance(column.type, Integer), f"{model.__tablename__}.{name}"
        assert not isinstance(column.type, BigInteger), f"{model.__tablename__}.{name}"
