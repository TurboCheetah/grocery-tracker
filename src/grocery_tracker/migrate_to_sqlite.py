"""Migration script from JSON to SQLite data storage.

This script migrates existing JSON data files to the new SQLite database.
It can be run safely multiple times - it will detect if migration has already
occurred and skip if the database already has data.
"""

import json
from pathlib import Path

from .data_store import DataStore
from .models import (
    BudgetTracking,
    CategoryBudget,
)
from .sqlite_store import SQLiteStore


class MigrationError(Exception):
    """Raised when migration encounters an error."""
    pass


class JSONToSQLiteMigrator:
    """Migrates data from JSON files to SQLite database."""

    def __init__(
        self,
        json_data_dir: Path | None = None,
        sqlite_db_path: Path | None = None,
    ):
        """Initialize migrator.

        Args:
            json_data_dir: Directory containing JSON data files.
                          Defaults to ./data
            sqlite_db_path: Path to SQLite database file.
                           Defaults to ./data/grocery.db
        """
        self.json_data_dir = json_data_dir or Path.cwd() / "data"
        self.sqlite_db_path = sqlite_db_path or (self.json_data_dir / "grocery.db")

        self.json_store = DataStore(data_dir=self.json_data_dir)
        self.sqlite_store = SQLiteStore(db_path=self.sqlite_db_path)

        self.stats = {
            "grocery_items": 0,
            "receipts": 0,
            "price_points": 0,
            "frequency_items": 0,
            "purchase_records": 0,
            "out_of_stock": 0,
            "inventory_items": 0,
            "waste_records": 0,
            "budgets": 0,
            "users": 0,
        }

    def check_json_data_exists(self) -> bool:
        """Check if there is JSON data to migrate.

        Returns:
            True if any JSON data files exist
        """
        json_files = [
            self.json_data_dir / "current_list.json",
            self.json_data_dir / "price_history.json",
            self.json_data_dir / "frequency_data.json",
            self.json_data_dir / "out_of_stock.json",
            self.json_data_dir / "inventory.json",
            self.json_data_dir / "waste_log.json",
            self.json_data_dir / "budget.json",
            self.json_data_dir / "user_preferences.json",
        ]

        receipts_dir = self.json_data_dir / "receipts"

        has_files = any(f.exists() for f in json_files)
        has_receipts = receipts_dir.exists() and any(receipts_dir.glob("*.json"))

        return has_files or has_receipts

    def check_sqlite_has_data(self) -> bool:
        """Check if SQLite database already has data.

        Returns:
            True if database has existing data
        """
        grocery_list = self.sqlite_store.load_list()
        receipts = self.sqlite_store.list_receipts()

        return len(grocery_list.items) > 0 or len(receipts) > 0

    def migrate_grocery_list(self) -> int:
        """Migrate grocery list items.

        Returns:
            Number of items migrated
        """
        grocery_list = self.json_store.load_list()
        if grocery_list.items:
            self.sqlite_store.save_list(grocery_list)

        count = len(grocery_list.items)
        self.stats["grocery_items"] = count
        return count

    def migrate_receipts(self) -> int:
        """Migrate receipts.

        Returns:
            Number of receipts migrated
        """
        receipts = self.json_store.list_receipts()

        for receipt in receipts:
            self.sqlite_store.save_receipt(receipt)

        count = len(receipts)
        self.stats["receipts"] = count
        return count

    def migrate_price_history(self) -> tuple[int, int]:
        """Migrate price history.

        Returns:
            Tuple of (items_count, price_points_count)
        """
        history = self.json_store.load_price_history()

        if history:
            self.sqlite_store.save_price_history(history)

        items_count = len(history)
        points_count = sum(
            len(store_history.price_points)
            for item_stores in history.values()
            for store_history in item_stores.values()
        )

        self.stats["price_points"] = points_count
        return items_count, points_count

    def migrate_frequency_data(self) -> tuple[int, int]:
        """Migrate frequency data.

        Returns:
            Tuple of (items_count, records_count)
        """
        frequency = self.json_store.load_frequency_data()

        if frequency:
            self.sqlite_store.save_frequency_data(frequency)

        items_count = len(frequency)
        records_count = sum(
            len(freq.purchase_history)
            for freq in frequency.values()
        )

        self.stats["frequency_items"] = items_count
        self.stats["purchase_records"] = records_count
        return items_count, records_count

    def migrate_out_of_stock(self) -> int:
        """Migrate out-of-stock records.

        Returns:
            Number of records migrated
        """
        records = self.json_store.load_out_of_stock()

        if records:
            self.sqlite_store.save_out_of_stock(records)

        count = len(records)
        self.stats["out_of_stock"] = count
        return count

    def migrate_inventory(self) -> int:
        """Migrate inventory items.

        Returns:
            Number of items migrated
        """
        items = self.json_store.load_inventory()

        if items:
            self.sqlite_store.save_inventory(items)

        count = len(items)
        self.stats["inventory_items"] = count
        return count

    def migrate_waste_log(self) -> int:
        """Migrate waste log records.

        Returns:
            Number of records migrated
        """
        records = self.json_store.load_waste_log()

        if records:
            self.sqlite_store.save_waste_log(records)

        count = len(records)
        self.stats["waste_records"] = count
        return count

    def migrate_budgets(self) -> int:
        """Migrate budget data.

        Returns:
            Number of budgets migrated
        """
        budget_path = self.json_data_dir / "budget.json"
        if not budget_path.exists():
            return 0

        with open(budget_path) as f:
            all_budgets = json.load(f)

        count = 0
        for month, budget_data in all_budgets.items():
            cat_budgets = [
                CategoryBudget(**cb)
                for cb in budget_data.get("category_budgets", [])
            ]

            budget = BudgetTracking(
                month=month,
                monthly_limit=budget_data.get("monthly_limit", 0.0),
                category_budgets=cat_budgets,
                total_spent=budget_data.get("total_spent", 0.0),
            )

            self.sqlite_store.save_budget(budget)
            count += 1

        self.stats["budgets"] = count
        return count

    def migrate_user_preferences(self) -> int:
        """Migrate user preferences.

        Returns:
            Number of users migrated
        """
        preferences = self.json_store.load_preferences()

        if preferences:
            self.sqlite_store.save_preferences(preferences)

        count = len(preferences)
        self.stats["users"] = count
        return count

    def verify_migration(self) -> dict[str, bool]:
        """Verify that data was migrated correctly.

        Returns:
            Dict mapping data type to verification result
        """
        results = {}

        # Verify grocery list
        json_list = self.json_store.load_list()
        sqlite_list = self.sqlite_store.load_list()
        results["grocery_items"] = len(json_list.items) == len(sqlite_list.items)

        # Verify receipts
        json_receipts = self.json_store.list_receipts()
        sqlite_receipts = self.sqlite_store.list_receipts()
        results["receipts"] = len(json_receipts) == len(sqlite_receipts)

        # Verify price history
        json_history = self.json_store.load_price_history()
        sqlite_history = self.sqlite_store.load_price_history()
        results["price_history"] = len(json_history) == len(sqlite_history)

        # Verify frequency data
        json_freq = self.json_store.load_frequency_data()
        sqlite_freq = self.sqlite_store.load_frequency_data()
        results["frequency_data"] = len(json_freq) == len(sqlite_freq)

        # Verify out of stock
        json_oos = self.json_store.load_out_of_stock()
        sqlite_oos = self.sqlite_store.load_out_of_stock()
        results["out_of_stock"] = len(json_oos) == len(sqlite_oos)

        # Verify inventory
        json_inv = self.json_store.load_inventory()
        sqlite_inv = self.sqlite_store.load_inventory()
        results["inventory"] = len(json_inv) == len(sqlite_inv)

        # Verify waste log
        json_waste = self.json_store.load_waste_log()
        sqlite_waste = self.sqlite_store.load_waste_log()
        results["waste_log"] = len(json_waste) == len(sqlite_waste)

        # Verify user preferences
        json_prefs = self.json_store.load_preferences()
        sqlite_prefs = self.sqlite_store.load_preferences()
        results["user_preferences"] = len(json_prefs) == len(sqlite_prefs)

        return results

    def run_migration(self, force: bool = False) -> dict[str, int]:
        """Run the full migration.

        Args:
            force: If True, migrate even if SQLite already has data

        Returns:
            Dict with migration statistics

        Raises:
            MigrationError: If migration fails or data verification fails
        """
        # Check if JSON data exists
        if not self.check_json_data_exists():
            print("No JSON data found to migrate.")
            return self.stats

        # Check if SQLite already has data
        if self.check_sqlite_has_data() and not force:
            print("SQLite database already contains data.")
            print("Use force=True to overwrite existing data.")
            return self.stats

        print(f"Starting migration from {self.json_data_dir} to {self.sqlite_db_path}")
        print()

        # Run migrations
        print("Migrating grocery list...", end=" ")
        items = self.migrate_grocery_list()
        print(f"{items} items")

        print("Migrating receipts...", end=" ")
        receipts = self.migrate_receipts()
        print(f"{receipts} receipts")

        print("Migrating price history...", end=" ")
        items, points = self.migrate_price_history()
        print(f"{items} items, {points} price points")

        print("Migrating frequency data...", end=" ")
        items, records = self.migrate_frequency_data()
        print(f"{items} items, {records} records")

        print("Migrating out-of-stock records...", end=" ")
        oos = self.migrate_out_of_stock()
        print(f"{oos} records")

        print("Migrating inventory...", end=" ")
        inv = self.migrate_inventory()
        print(f"{inv} items")

        print("Migrating waste log...", end=" ")
        waste = self.migrate_waste_log()
        print(f"{waste} records")

        print("Migrating budgets...", end=" ")
        budgets = self.migrate_budgets()
        print(f"{budgets} budgets")

        print("Migrating user preferences...", end=" ")
        users = self.migrate_user_preferences()
        print(f"{users} users")

        print()
        print("Verifying migration...")
        verification = self.verify_migration()

        all_verified = all(verification.values())
        if not all_verified:
            failed = [k for k, v in verification.items() if not v]
            raise MigrationError(f"Migration verification failed for: {failed}")

        print("All data verified successfully!")
        print()
        print("Migration complete!")
        print(f"  Database: {self.sqlite_db_path}")

        return self.stats


def migrate(
    data_dir: Path | None = None,
    db_path: Path | None = None,
    force: bool = False,
) -> dict[str, int]:
    """Convenience function to run migration.

    Args:
        data_dir: Directory containing JSON data files
        db_path: Path to SQLite database file
        force: If True, overwrite existing SQLite data

    Returns:
        Migration statistics
    """
    migrator = JSONToSQLiteMigrator(
        json_data_dir=data_dir,
        sqlite_db_path=db_path,
    )
    return migrator.run_migration(force=force)


if __name__ == "__main__":
    import sys

    force = "--force" in sys.argv
    stats = migrate(force=force)

    print("\nMigration Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
