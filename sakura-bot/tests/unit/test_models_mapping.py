"""ORM mapping regressions for the declarative models."""
from models.base import Base
from models.user import UserInventory

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
