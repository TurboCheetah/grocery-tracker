"""Tests for SQLite data store implementation."""

from datetime import date, time
from uuid import uuid4

import pytest

from grocery_tracker.data_store import BackendType, create_data_store
from grocery_tracker.models import (
    BudgetTracking,
    CategoryBudget,
    FrequencyData,
    GroceryItem,
    GroceryList,
    InventoryItem,
    InventoryLocation,
    ItemStatus,
    LineItem,
    OutOfStockRecord,
    PriceHistory,
    PricePoint,
    Priority,
    PurchaseRecord,
    Receipt,
    UserPreferences,
    WasteReason,
    WasteRecord,
)
from grocery_tracker.sqlite_store import SQLiteStore


@pytest.fixture
def sqlite_store(tmp_path):
    """Create a SQLite store with a temporary database."""
    db_path = tmp_path / "test.db"
    return SQLiteStore(db_path=db_path)


@pytest.fixture
def sample_item():
    """Create a sample grocery item."""
    return GroceryItem(
        name="Bananas",
        quantity=3,
        unit="bunch",
        category="Produce",
        store="Giant",
        aisle="1",
        brand_preference=None,
        estimated_price=2.99,
        priority=Priority.MEDIUM,
        added_by="Alice",
        notes="Ripe ones",
        status=ItemStatus.TO_BUY,
    )


@pytest.fixture
def sample_receipt():
    """Create a sample receipt."""
    return Receipt(
        store_name="Giant Food",
        store_location="Rockville, MD",
        transaction_date=date(2026, 1, 25),
        transaction_time=time(14, 32),
        purchased_by="Alice",
        line_items=[
            LineItem(
                item_name="Bananas",
                quantity=3,
                unit_price=0.49,
                total_price=1.47,
            ),
            LineItem(
                item_name="Milk",
                quantity=1,
                unit_price=5.49,
                total_price=5.49,
            ),
        ],
        subtotal=6.96,
        tax=0.0,
        total=6.96,
        payment_method="Credit",
    )


class TestSQLiteStoreCreation:
    """Tests for SQLite store initialization."""

    def test_create_store(self, tmp_path):
        """Test that store can be created."""
        db_path = tmp_path / "test.db"
        SQLiteStore(db_path=db_path)
        assert db_path.exists()

    def test_create_store_creates_directories(self, tmp_path):
        """Test that store creates parent directories."""
        db_path = tmp_path / "nested" / "dir" / "test.db"
        SQLiteStore(db_path=db_path)
        assert db_path.exists()

    def test_create_store_via_factory(self, tmp_path):
        """Test creating store via factory function."""
        db_path = tmp_path / "factory.db"
        create_data_store(BackendType.SQLITE, db_path=db_path)
        assert db_path.exists()


class TestGroceryListOperations:
    """Tests for grocery list CRUD operations."""

    def test_save_and_load_empty_list(self, sqlite_store):
        """Test saving and loading an empty list."""
        grocery_list = GroceryList()
        sqlite_store.save_list(grocery_list)

        loaded = sqlite_store.load_list()
        assert loaded.version == "1.0"
        assert len(loaded.items) == 0

    def test_save_and_load_list_with_items(self, sqlite_store, sample_item):
        """Test saving and loading a list with items."""
        grocery_list = GroceryList(items=[sample_item])
        sqlite_store.save_list(grocery_list)

        loaded = sqlite_store.load_list()
        assert len(loaded.items) == 1
        assert loaded.items[0].name == "Bananas"
        assert loaded.items[0].quantity == 3
        assert loaded.items[0].store == "Giant"

    def test_update_list_removes_deleted_items(self, sqlite_store, sample_item):
        """Test that updating list removes items not in new list."""
        # Save list with item
        grocery_list = GroceryList(items=[sample_item])
        sqlite_store.save_list(grocery_list)

        # Save empty list
        sqlite_store.save_list(GroceryList())

        loaded = sqlite_store.load_list()
        assert len(loaded.items) == 0

    def test_get_item_by_id(self, sqlite_store, sample_item):
        """Test getting a specific item by ID."""
        grocery_list = GroceryList(items=[sample_item])
        sqlite_store.save_list(grocery_list)

        item = sqlite_store.get_item(sample_item.id)
        assert item is not None
        assert item.name == "Bananas"

    def test_get_item_not_found(self, sqlite_store):
        """Test getting non-existent item returns None."""
        item = sqlite_store.get_item(uuid4())
        assert item is None

    def test_quantity_types_preserved(self, sqlite_store):
        """Test that different quantity types are preserved."""
        items = [
            GroceryItem(name="Eggs", quantity=12),  # int
            GroceryItem(name="Milk", quantity=1.5),  # float
            GroceryItem(name="Cheese", quantity="1 lb"),  # string
        ]
        grocery_list = GroceryList(items=items)
        sqlite_store.save_list(grocery_list)

        loaded = sqlite_store.load_list()
        # Find items by name since order may vary
        eggs = next(i for i in loaded.items if i.name == "Eggs")
        milk = next(i for i in loaded.items if i.name == "Milk")
        cheese = next(i for i in loaded.items if i.name == "Cheese")

        assert eggs.quantity == 12
        assert milk.quantity == 1.5
        assert cheese.quantity == "1 lb"


class TestReceiptOperations:
    """Tests for receipt CRUD operations."""

    def test_save_and_load_receipt(self, sqlite_store, sample_receipt):
        """Test saving and loading a receipt."""
        receipt_id = sqlite_store.save_receipt(sample_receipt)

        loaded = sqlite_store.load_receipt(receipt_id)
        assert loaded is not None
        assert loaded.store_name == "Giant Food"
        assert loaded.total == 6.96
        assert len(loaded.line_items) == 2

    def test_load_receipt_not_found(self, sqlite_store):
        """Test loading non-existent receipt returns None."""
        loaded = sqlite_store.load_receipt(uuid4())
        assert loaded is None

    def test_list_receipts(self, sqlite_store, sample_receipt):
        """Test listing all receipts."""
        sqlite_store.save_receipt(sample_receipt)

        # Create another receipt
        receipt2 = Receipt(
            store_name="Trader Joe's",
            transaction_date=date(2026, 1, 26),
            line_items=[
                LineItem(item_name="Avocados", quantity=2, unit_price=1.49, total_price=2.98),
            ],
            subtotal=2.98,
            total=2.98,
        )
        sqlite_store.save_receipt(receipt2)

        receipts = sqlite_store.list_receipts()
        assert len(receipts) == 2
        # Should be sorted by date descending
        assert receipts[0].transaction_date >= receipts[1].transaction_date

    def test_receipt_line_items_with_matched_id(self, sqlite_store, sample_item, sample_receipt):
        """Test receipt line items can reference list items."""
        # Save item first
        grocery_list = GroceryList(items=[sample_item])
        sqlite_store.save_list(grocery_list)

        # Update receipt to match the item
        sample_receipt.line_items[0].matched_list_item_id = sample_item.id
        sqlite_store.save_receipt(sample_receipt)

        loaded = sqlite_store.load_receipt(sample_receipt.id)
        assert loaded.line_items[0].matched_list_item_id == sample_item.id


class TestPriceHistoryOperations:
    """Tests for price history operations."""

    def test_update_price(self, sqlite_store):
        """Test updating price history."""
        sqlite_store.update_price(
            item_name="Milk",
            store="Giant",
            price=5.49,
            purchase_date=date(2026, 1, 25),
        )

        history = sqlite_store.get_price_history("Milk", "Giant")
        assert history is not None
        assert len(history.price_points) == 1
        assert history.price_points[0].price == 5.49

    def test_multiple_price_points(self, sqlite_store):
        """Test multiple price points for same item."""
        sqlite_store.update_price("Eggs", "Giant", 4.99, date(2026, 1, 20))
        sqlite_store.update_price("Eggs", "Giant", 5.49, date(2026, 1, 25))
        sqlite_store.update_price("Eggs", "Giant", 4.49, date(2026, 1, 27), sale=True)

        history = sqlite_store.get_price_history("Eggs", "Giant")
        assert len(history.price_points) == 3

    def test_price_history_across_stores(self, sqlite_store):
        """Test price history for same item at different stores."""
        sqlite_store.update_price("Milk", "Giant", 5.49, date(2026, 1, 25))
        sqlite_store.update_price("Milk", "Trader Joe's", 4.99, date(2026, 1, 25))

        # Get combined history
        history = sqlite_store.get_price_history("Milk")
        assert len(history.price_points) == 2

        # Get store-specific history
        giant_history = sqlite_store.get_price_history("Milk", "Giant")
        assert len(giant_history.price_points) == 1
        assert giant_history.price_points[0].price == 5.49

    def test_save_and_load_price_history(self, sqlite_store):
        """Test bulk save and load of price history."""
        history = {
            "Milk": {
                "Giant": PriceHistory(
                    item_name="Milk",
                    store="Giant",
                    price_points=[
                        PricePoint(date=date(2026, 1, 25), price=5.49),
                    ],
                ),
            },
        }
        sqlite_store.save_price_history(history)

        loaded = sqlite_store.load_price_history()
        assert "Milk" in loaded
        assert "Giant" in loaded["Milk"]


class TestFrequencyDataOperations:
    """Tests for frequency data operations."""

    def test_update_frequency(self, sqlite_store):
        """Test updating frequency data."""
        sqlite_store.update_frequency(
            item_name="Milk",
            purchase_date=date(2026, 1, 25),
            quantity=1.0,
            store="Giant",
            category="Dairy",
        )

        freq = sqlite_store.get_frequency("Milk")
        assert freq is not None
        assert freq.category == "Dairy"
        assert len(freq.purchase_history) == 1

    def test_multiple_purchases(self, sqlite_store):
        """Test recording multiple purchases."""
        sqlite_store.update_frequency("Milk", date(2026, 1, 15))
        sqlite_store.update_frequency("Milk", date(2026, 1, 20))
        sqlite_store.update_frequency("Milk", date(2026, 1, 25))

        freq = sqlite_store.get_frequency("Milk")
        assert len(freq.purchase_history) == 3

    def test_save_and_load_frequency_data(self, sqlite_store):
        """Test bulk save and load of frequency data."""
        frequency = {
            "Milk": FrequencyData(
                item_name="Milk",
                category="Dairy",
                purchase_history=[
                    PurchaseRecord(date=date(2026, 1, 25), quantity=1.0, store="Giant"),
                ],
            ),
        }
        sqlite_store.save_frequency_data(frequency)

        loaded = sqlite_store.load_frequency_data()
        assert "Milk" in loaded
        assert len(loaded["Milk"].purchase_history) == 1


class TestOutOfStockOperations:
    """Tests for out-of-stock operations."""

    def test_add_out_of_stock(self, sqlite_store):
        """Test adding out-of-stock record."""
        record = OutOfStockRecord(
            item_name="Oat Milk",
            store="Giant",
            recorded_date=date(2026, 1, 25),
            substitution="Almond Milk",
            reported_by="Alice",
        )
        sqlite_store.add_out_of_stock(record)

        records = sqlite_store.load_out_of_stock()
        assert len(records) == 1
        assert records[0].item_name == "Oat Milk"

    def test_get_out_of_stock_for_item(self, sqlite_store):
        """Test filtering out-of-stock by item."""
        sqlite_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="Giant", recorded_date=date(2026, 1, 25))
        )
        sqlite_store.add_out_of_stock(
            OutOfStockRecord(
                item_name="Oat Milk", store="Trader Joe's", recorded_date=date(2026, 1, 26)
            )
        )
        sqlite_store.add_out_of_stock(
            OutOfStockRecord(
                item_name="Almond Milk", store="Giant", recorded_date=date(2026, 1, 25)
            )
        )

        # All records for oat milk
        records = sqlite_store.get_out_of_stock_for_item("Oat Milk")
        assert len(records) == 2

        # Filter by store
        records = sqlite_store.get_out_of_stock_for_item("Oat Milk", "Giant")
        assert len(records) == 1


class TestInventoryOperations:
    """Tests for inventory operations."""

    def test_save_and_load_inventory(self, sqlite_store):
        """Test saving and loading inventory."""
        items = [
            InventoryItem(
                item_name="Milk",
                category="Dairy",
                quantity=1.0,
                unit="gallon",
                location=InventoryLocation.FRIDGE,
                expiration_date=date(2026, 2, 1),
                purchased_date=date(2026, 1, 25),
            ),
            InventoryItem(
                item_name="Rice",
                category="Pantry",
                quantity=2.0,
                unit="lbs",
                location=InventoryLocation.PANTRY,
                purchased_date=date(2026, 1, 20),
            ),
        ]
        sqlite_store.save_inventory(items)

        loaded = sqlite_store.load_inventory()
        assert len(loaded) == 2
        milk = next(i for i in loaded if i.item_name == "Milk")
        assert milk.location == InventoryLocation.FRIDGE
        assert milk.expiration_date == date(2026, 2, 1)


class TestWasteLogOperations:
    """Tests for waste log operations."""

    def test_add_waste_record(self, sqlite_store):
        """Test adding waste record."""
        record = WasteRecord(
            item_name="Lettuce",
            quantity=1.0,
            unit="head",
            original_purchase_date=date(2026, 1, 20),
            waste_logged_date=date(2026, 1, 28),
            reason=WasteReason.SPOILED,
            estimated_cost=2.99,
            logged_by="Alice",
        )
        sqlite_store.add_waste_record(record)

        records = sqlite_store.load_waste_log()
        assert len(records) == 1
        assert records[0].item_name == "Lettuce"
        assert records[0].reason == WasteReason.SPOILED

    def test_save_and_load_waste_log(self, sqlite_store):
        """Test bulk save and load of waste log."""
        records = [
            WasteRecord(
                item_name="Lettuce",
                quantity=1.0,
                reason=WasteReason.SPOILED,
            ),
            WasteRecord(
                item_name="Bread",
                quantity=0.5,
                unit="loaf",
                reason=WasteReason.NEVER_USED,
            ),
        ]
        sqlite_store.save_waste_log(records)

        loaded = sqlite_store.load_waste_log()
        assert len(loaded) == 2


class TestBudgetOperations:
    """Tests for budget operations."""

    def test_save_and_load_budget(self, sqlite_store):
        """Test saving and loading budget."""
        budget = BudgetTracking(
            month="2026-01",
            monthly_limit=500.0,
            total_spent=125.50,
            category_budgets=[
                CategoryBudget(category="Produce", limit=100.0, spent=45.0),
                CategoryBudget(category="Dairy", limit=75.0, spent=30.0),
            ],
        )
        sqlite_store.save_budget(budget)

        loaded = sqlite_store.load_budget("2026-01")
        assert loaded is not None
        assert loaded.monthly_limit == 500.0
        assert loaded.total_spent == 125.50
        assert len(loaded.category_budgets) == 2

    def test_load_budget_not_found(self, sqlite_store):
        """Test loading non-existent budget returns None."""
        loaded = sqlite_store.load_budget("2025-01")
        assert loaded is None


class TestUserPreferencesOperations:
    """Tests for user preferences operations."""

    def test_save_and_load_user_preferences(self, sqlite_store):
        """Test saving and loading user preferences."""
        prefs = UserPreferences(
            user="Alice",
            brand_preferences={"milk": "Organic Valley", "eggs": "Vital Farms"},
            dietary_restrictions=["dairy-free"],
            allergens=["peanuts"],
            favorite_items=["avocados", "dark chocolate"],
            shopping_patterns={"typical_day": "Saturday"},
        )
        sqlite_store.save_user_preferences(prefs)

        loaded = sqlite_store.get_user_preferences("Alice")
        assert loaded is not None
        assert loaded.brand_preferences["milk"] == "Organic Valley"
        assert "dairy-free" in loaded.dietary_restrictions
        assert "peanuts" in loaded.allergens

    def test_get_user_preferences_not_found(self, sqlite_store):
        """Test getting non-existent user returns None."""
        loaded = sqlite_store.get_user_preferences("NonExistent")
        assert loaded is None

    def test_save_and_load_all_preferences(self, sqlite_store):
        """Test bulk save and load of preferences."""
        preferences = {
            "Alice": UserPreferences(
                user="Alice",
                brand_preferences={"milk": "Organic Valley"},
            ),
            "Bob": UserPreferences(
                user="Bob",
                dietary_restrictions=["vegetarian"],
            ),
        }
        sqlite_store.save_preferences(preferences)

        loaded = sqlite_store.load_preferences()
        assert "Alice" in loaded
        assert "Bob" in loaded
        assert loaded["Bob"].dietary_restrictions == ["vegetarian"]


class TestDataIntegrity:
    """Tests for data integrity across operations."""

    def test_concurrent_list_updates(self, sqlite_store, sample_item):
        """Test that concurrent updates don't lose data."""
        for i in range(10):
            item = GroceryItem(name=f"Item {i}", quantity=i + 1)
            grocery_list = sqlite_store.load_list()
            grocery_list.items.append(item)
            sqlite_store.save_list(grocery_list)

        final_list = sqlite_store.load_list()
        assert len(final_list.items) == 10

    def test_special_characters_in_names(self, sqlite_store):
        """Test handling of special characters."""
        item = GroceryItem(
            name="Ben & Jerry's Ice Cream",
            quantity=1,
            notes='Get the "Half Baked" flavor',
        )
        grocery_list = GroceryList(items=[item])
        sqlite_store.save_list(grocery_list)

        loaded = sqlite_store.load_list()
        assert loaded.items[0].name == "Ben & Jerry's Ice Cream"
        assert "Half Baked" in loaded.items[0].notes

    def test_unicode_characters(self, sqlite_store):
        """Test handling of unicode characters."""
        item = GroceryItem(name="Café Latte Beans", quantity=1)
        grocery_list = GroceryList(items=[item])
        sqlite_store.save_list(grocery_list)

        loaded = sqlite_store.load_list()
        assert loaded.items[0].name == "Café Latte Beans"
