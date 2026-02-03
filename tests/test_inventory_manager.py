"""Tests for inventory manager module."""

from datetime import date, timedelta
from uuid import UUID

import pytest

from grocery_tracker.inventory_manager import InventoryManager
from grocery_tracker.models import InventoryLocation


@pytest.fixture
def inv_manager(data_store):
    """Create an InventoryManager with test data store."""
    return InventoryManager(data_store=data_store)


class TestAddItem:
    """Tests for adding inventory items."""

    def test_add_basic(self, inv_manager):
        """Add a basic item to inventory."""
        item = inv_manager.add_item(item_name="Milk", quantity=1.0)
        assert item.item_name == "Milk"
        assert item.quantity == 1.0
        assert isinstance(item.id, UUID)

    def test_add_with_all_fields(self, inv_manager):
        """Add an item with all fields populated."""
        exp = date.today() + timedelta(days=7)
        item = inv_manager.add_item(
            item_name="Yogurt",
            quantity=3.0,
            unit="cups",
            category="Dairy & Eggs",
            location=InventoryLocation.FRIDGE,
            expiration_date=exp,
            low_stock_threshold=2.0,
            added_by="Francisco",
        )
        assert item.item_name == "Yogurt"
        assert item.location == InventoryLocation.FRIDGE
        assert item.expiration_date == exp
        assert item.low_stock_threshold == 2.0
        assert item.added_by == "Francisco"

    def test_add_persists(self, inv_manager, data_store):
        """Added items persist to data store."""
        inv_manager.add_item(item_name="Rice")
        inventory = data_store.load_inventory()
        assert len(inventory) == 1
        assert inventory[0].item_name == "Rice"

    def test_add_multiple(self, inv_manager):
        """Can add multiple items."""
        inv_manager.add_item(item_name="Milk")
        inv_manager.add_item(item_name="Eggs")
        inv_manager.add_item(item_name="Bread")
        items = inv_manager.get_inventory()
        assert len(items) == 3


class TestRemoveItem:
    """Tests for removing inventory items."""

    def test_remove_by_id(self, inv_manager):
        """Remove an item by UUID."""
        item = inv_manager.add_item(item_name="Milk")
        removed = inv_manager.remove_item(str(item.id))
        assert removed.item_name == "Milk"
        assert len(inv_manager.get_inventory()) == 0

    def test_remove_not_found(self, inv_manager):
        """Raises ValueError for unknown ID."""
        with pytest.raises(ValueError, match="Inventory item not found"):
            inv_manager.remove_item("00000000-0000-0000-0000-000000000000")


class TestUpdateQuantity:
    """Tests for updating item quantity."""

    def test_set_quantity(self, inv_manager):
        """Set absolute quantity."""
        item = inv_manager.add_item(item_name="Milk", quantity=2.0)
        updated = inv_manager.update_quantity(str(item.id), quantity=5.0)
        assert updated.quantity == 5.0

    def test_delta_positive(self, inv_manager):
        """Add to quantity with delta."""
        item = inv_manager.add_item(item_name="Eggs", quantity=6.0)
        updated = inv_manager.update_quantity(str(item.id), delta=6.0)
        assert updated.quantity == 12.0

    def test_delta_negative(self, inv_manager):
        """Subtract from quantity with delta."""
        item = inv_manager.add_item(item_name="Eggs", quantity=12.0)
        updated = inv_manager.update_quantity(str(item.id), delta=-4.0)
        assert updated.quantity == 8.0

    def test_delta_floor_zero(self, inv_manager):
        """Delta can't go below zero."""
        item = inv_manager.add_item(item_name="Milk", quantity=1.0)
        updated = inv_manager.update_quantity(str(item.id), delta=-5.0)
        assert updated.quantity == 0.0

    def test_no_args_raises(self, inv_manager):
        """Raises ValueError if neither quantity nor delta provided."""
        item = inv_manager.add_item(item_name="Milk")
        with pytest.raises(ValueError, match="Must provide quantity or delta"):
            inv_manager.update_quantity(str(item.id))

    def test_not_found(self, inv_manager):
        """Raises ValueError for unknown ID."""
        with pytest.raises(ValueError, match="Inventory item not found"):
            inv_manager.update_quantity("00000000-0000-0000-0000-000000000000", quantity=1.0)


class TestGetInventory:
    """Tests for listing inventory."""

    def test_empty(self, inv_manager):
        """Empty inventory returns empty list."""
        assert inv_manager.get_inventory() == []

    def test_filter_by_location(self, inv_manager):
        """Filter by storage location."""
        inv_manager.add_item(item_name="Milk", location=InventoryLocation.FRIDGE)
        inv_manager.add_item(item_name="Rice", location=InventoryLocation.PANTRY)
        inv_manager.add_item(item_name="Ice Cream", location=InventoryLocation.FREEZER)

        fridge = inv_manager.get_inventory(location=InventoryLocation.FRIDGE)
        assert len(fridge) == 1
        assert fridge[0].item_name == "Milk"

    def test_filter_by_category(self, inv_manager):
        """Filter by category."""
        inv_manager.add_item(item_name="Milk", category="Dairy & Eggs")
        inv_manager.add_item(item_name="Rice", category="Pantry & Canned Goods")

        dairy = inv_manager.get_inventory(category="Dairy & Eggs")
        assert len(dairy) == 1
        assert dairy[0].item_name == "Milk"


class TestExpiringAndLowStock:
    """Tests for expiring and low stock queries."""

    def test_expiring_soon(self, inv_manager):
        """Get items expiring within N days."""
        tomorrow = date.today() + timedelta(days=1)
        next_week = date.today() + timedelta(days=7)

        inv_manager.add_item(item_name="Milk", expiration_date=tomorrow)
        inv_manager.add_item(item_name="Cheese", expiration_date=next_week)
        inv_manager.add_item(item_name="Rice")  # no expiration

        expiring = inv_manager.get_expiring_soon(days=3)
        assert len(expiring) == 1
        assert expiring[0].item_name == "Milk"

    def test_expiring_includes_expired(self, inv_manager):
        """Expired items show up in expiring soon."""
        yesterday = date.today() - timedelta(days=1)
        inv_manager.add_item(item_name="Milk", expiration_date=yesterday)

        expiring = inv_manager.get_expiring_soon(days=3)
        assert len(expiring) == 1

    def test_low_stock(self, inv_manager):
        """Get items below low stock threshold."""
        inv_manager.add_item(item_name="Eggs", quantity=1.0, low_stock_threshold=3.0)
        inv_manager.add_item(item_name="Milk", quantity=5.0, low_stock_threshold=1.0)

        low = inv_manager.get_low_stock()
        assert len(low) == 1
        assert low[0].item_name == "Eggs"

    def test_low_stock_at_threshold(self, inv_manager):
        """Items at exactly the threshold count as low stock."""
        inv_manager.add_item(item_name="Eggs", quantity=3.0, low_stock_threshold=3.0)

        low = inv_manager.get_low_stock()
        assert len(low) == 1


class TestAddFromReceipt:
    """Tests for adding inventory from receipt."""

    def test_add_from_receipt(self, inv_manager):
        """Adds items from a receipt object."""
        from grocery_tracker.models import LineItem, Receipt

        receipt = Receipt(
            store_name="Giant",
            transaction_date=date.today(),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49),
                LineItem(item_name="Eggs", quantity=12, unit_price=0.33, total_price=3.99),
            ],
            subtotal=9.48,
            total=9.48,
        )

        added = inv_manager.add_from_receipt(receipt)
        assert len(added) == 2
        assert added[0].item_name == "Milk"
        assert added[1].item_name == "Eggs"
        assert added[1].quantity == 12
