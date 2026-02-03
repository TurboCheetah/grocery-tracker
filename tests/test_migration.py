"""Tests for JSON to SQLite migration."""

import pytest
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from grocery_tracker.migrate_to_sqlite import JSONToSQLiteMigrator, migrate, MigrationError
from grocery_tracker.data_store import DataStore
from grocery_tracker.sqlite_store import SQLiteStore
from grocery_tracker.models import (
    GroceryItem,
    GroceryList,
    Receipt,
    LineItem,
    PriceHistory,
    PricePoint,
    FrequencyData,
    PurchaseRecord,
    OutOfStockRecord,
    InventoryItem,
    InventoryLocation,
    WasteRecord,
    WasteReason,
    CategoryBudget,
    BudgetTracking,
    UserPreferences,
)


@pytest.fixture
def json_store(tmp_path):
    """Create a JSON store with test data."""
    data_dir = tmp_path / "json_data"
    store = DataStore(data_dir=data_dir)
    return store


@pytest.fixture
def populated_json_store(json_store):
    """Create a JSON store with populated test data."""
    # Add grocery items
    items = [
        GroceryItem(name="Bananas", quantity=3, store="Giant", category="Produce"),
        GroceryItem(name="Milk", quantity=1, store="Giant", category="Dairy"),
    ]
    json_store.save_list(GroceryList(items=items))

    # Add receipt
    receipt = Receipt(
        store_name="Giant Food",
        transaction_date=date(2026, 1, 25),
        line_items=[
            LineItem(item_name="Bananas", quantity=3, unit_price=0.49, total_price=1.47),
        ],
        subtotal=1.47,
        total=1.47,
    )
    json_store.save_receipt(receipt)

    # Add price history
    json_store.update_price("Bananas", "Giant", 0.49, date(2026, 1, 25))

    # Add frequency data
    json_store.update_frequency("Bananas", date(2026, 1, 25), category="Produce")

    # Add out of stock record
    json_store.add_out_of_stock(
        OutOfStockRecord(
            item_name="Oat Milk",
            store="Giant",
            recorded_date=date(2026, 1, 25),
        )
    )

    # Add inventory
    json_store.save_inventory(
        [
            InventoryItem(
                item_name="Rice",
                location=InventoryLocation.PANTRY,
                purchased_date=date(2026, 1, 20),
            ),
        ]
    )

    # Add waste record
    json_store.add_waste_record(
        WasteRecord(
            item_name="Lettuce",
            reason=WasteReason.SPOILED,
        )
    )

    # Add user preferences
    json_store.save_user_preferences(
        UserPreferences(
            user="Francisco",
            brand_preferences={"milk": "Organic Valley"},
        )
    )

    return json_store


class TestMigration:
    """Tests for migration functionality."""

    def test_check_json_data_exists_empty(self, tmp_path):
        """Test detecting no JSON data."""
        # Create the empty directory first
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        migrator = JSONToSQLiteMigrator(
            json_data_dir=empty_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        assert migrator.check_json_data_exists() is False

    def test_check_json_data_exists_with_data(self, populated_json_store, tmp_path):
        """Test detecting existing JSON data."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        assert migrator.check_json_data_exists() is True

    def test_migrate_grocery_list(self, populated_json_store, tmp_path):
        """Test migrating grocery list."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        count = migrator.migrate_grocery_list()
        assert count == 2

        # Verify data in SQLite
        sqlite_list = migrator.sqlite_store.load_list()
        assert len(sqlite_list.items) == 2

    def test_migrate_receipts(self, populated_json_store, tmp_path):
        """Test migrating receipts."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        count = migrator.migrate_receipts()
        assert count == 1

        # Verify data in SQLite
        sqlite_receipts = migrator.sqlite_store.list_receipts()
        assert len(sqlite_receipts) == 1
        assert sqlite_receipts[0].store_name == "Giant Food"

    def test_migrate_price_history(self, populated_json_store, tmp_path):
        """Test migrating price history."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        items_count, points_count = migrator.migrate_price_history()
        assert items_count == 1
        assert points_count == 1

    def test_migrate_frequency_data(self, populated_json_store, tmp_path):
        """Test migrating frequency data."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        items_count, records_count = migrator.migrate_frequency_data()
        assert items_count == 1
        assert records_count == 1

    def test_migrate_out_of_stock(self, populated_json_store, tmp_path):
        """Test migrating out-of-stock records."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        count = migrator.migrate_out_of_stock()
        assert count == 1

    def test_migrate_inventory(self, populated_json_store, tmp_path):
        """Test migrating inventory."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        count = migrator.migrate_inventory()
        assert count == 1

    def test_migrate_waste_log(self, populated_json_store, tmp_path):
        """Test migrating waste log."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        count = migrator.migrate_waste_log()
        assert count == 1

    def test_migrate_user_preferences(self, populated_json_store, tmp_path):
        """Test migrating user preferences."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        count = migrator.migrate_user_preferences()
        assert count == 1

    def test_full_migration(self, populated_json_store, tmp_path):
        """Test running full migration."""
        stats = migrate(
            data_dir=populated_json_store.data_dir,
            db_path=tmp_path / "test.db",
        )

        assert stats["grocery_items"] == 2
        assert stats["receipts"] == 1
        assert stats["out_of_stock"] == 1
        assert stats["inventory_items"] == 1
        assert stats["waste_records"] == 1
        assert stats["users"] == 1

    def test_verify_migration(self, populated_json_store, tmp_path):
        """Test migration verification."""
        migrator = JSONToSQLiteMigrator(
            json_data_dir=populated_json_store.data_dir,
            sqlite_db_path=tmp_path / "test.db",
        )

        migrator.run_migration()
        verification = migrator.verify_migration()

        assert verification["grocery_items"] is True
        assert verification["receipts"] is True
        assert verification["price_history"] is True
        assert verification["frequency_data"] is True
        assert verification["out_of_stock"] is True
        assert verification["inventory"] is True
        assert verification["waste_log"] is True
        assert verification["user_preferences"] is True

    def test_migration_skip_if_sqlite_has_data(self, populated_json_store, tmp_path):
        """Test migration skips if SQLite already has data."""
        # Run migration once
        migrate(
            data_dir=populated_json_store.data_dir,
            db_path=tmp_path / "test.db",
        )

        # Run again - should skip
        stats = migrate(
            data_dir=populated_json_store.data_dir,
            db_path=tmp_path / "test.db",
        )

        # Stats should be zero since migration was skipped
        assert stats["grocery_items"] == 0

    def test_migration_force_overwrite(self, populated_json_store, tmp_path):
        """Test migration with force flag overwrites existing data."""
        # Run migration once
        migrate(
            data_dir=populated_json_store.data_dir,
            db_path=tmp_path / "test.db",
        )

        # Run again with force
        stats = migrate(
            data_dir=populated_json_store.data_dir,
            db_path=tmp_path / "test.db",
            force=True,
        )

        assert stats["grocery_items"] == 2


class TestMigrationConvenienceFunction:
    """Tests for the migrate() convenience function."""

    def test_migrate_with_defaults(self, populated_json_store, tmp_path, monkeypatch):
        """Test migrate with default paths."""
        # Change cwd to tmp_path so default paths work
        monkeypatch.chdir(tmp_path)

        # Copy JSON data to expected location
        import shutil

        shutil.copytree(populated_json_store.data_dir, tmp_path / "data")

        stats = migrate()

        assert stats["grocery_items"] == 2
        assert (tmp_path / "data" / "grocery.db").exists()
