"""Tests for list manager operations."""

from uuid import uuid4

import pytest

from grocery_tracker.list_manager import (
    DuplicateItemError,
    ItemNotFoundError,
)
from grocery_tracker.models import ItemStatus, Priority


class TestAddItem:
    """Tests for adding items."""

    def test_add_item_minimal(self, list_manager):
        """Add item with only name."""
        result = list_manager.add_item(name="Milk")
        assert result["success"] is True
        assert "Added Milk" in result["message"]
        assert result["data"]["item"]["name"] == "Milk"

    def test_add_item_full(self, list_manager):
        """Add item with all fields."""
        result = list_manager.add_item(
            name="Organic Milk",
            quantity=2,
            store="Giant",
            category="Dairy",
            unit="gallon",
            brand_preference="Horizon",
            estimated_price=5.99,
            priority=Priority.HIGH,
            added_by="Alice",
            notes="Whole milk",
        )
        item = result["data"]["item"]
        assert item["name"] == "Organic Milk"
        assert item["quantity"] == 2
        assert item["store"] == "Giant"
        assert item["priority"] == "high"

    def test_add_duplicate_raises_error(self, list_manager):
        """Adding duplicate item raises error."""
        list_manager.add_item(name="Milk")
        with pytest.raises(DuplicateItemError) as exc_info:
            list_manager.add_item(name="Milk")
        assert "already exists" in str(exc_info.value)

    def test_add_duplicate_case_insensitive(self, list_manager):
        """Duplicate check is case insensitive."""
        list_manager.add_item(name="Milk")
        with pytest.raises(DuplicateItemError):
            list_manager.add_item(name="milk")

    def test_add_duplicate_with_force(self, list_manager):
        """Can add duplicate with force flag."""
        list_manager.add_item(name="Milk")
        result = list_manager.add_item(name="Milk", allow_duplicate=True)
        assert result["success"] is True

    def test_add_same_name_bought_item(self, list_manager):
        """Can add item with same name if existing is bought."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]
        list_manager.mark_bought(item_id)

        # Should not raise - existing item is bought
        result = list_manager.add_item(name="Milk")
        assert result["success"] is True


class TestRemoveItem:
    """Tests for removing items."""

    def test_remove_item(self, list_manager):
        """Remove existing item."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.remove_item(item_id)
        assert result["success"] is True
        assert "Removed Milk" in result["message"]

    def test_remove_nonexistent_raises_error(self, list_manager):
        """Removing non-existent item raises error."""
        with pytest.raises(ItemNotFoundError):
            list_manager.remove_item(str(uuid4()))

    def test_remove_item_string_id(self, list_manager):
        """Can remove item using string ID."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.remove_item(item_id)  # String ID
        assert result["success"] is True


class TestGetList:
    """Tests for getting the list."""

    def test_get_empty_list(self, list_manager):
        """Get empty list."""
        result = list_manager.get_list()
        assert result["success"] is True
        assert result["data"]["list"]["items"] == []
        assert result["data"]["list"]["total_items"] == 0

    def test_get_list_with_items(self, list_manager):
        """Get list with items."""
        list_manager.add_item(name="Milk")
        list_manager.add_item(name="Bread")

        result = list_manager.get_list()
        assert len(result["data"]["list"]["items"]) == 2

    def test_filter_by_store(self, list_manager):
        """Filter list by store."""
        list_manager.add_item(name="Milk", store="Giant")
        list_manager.add_item(name="Bread", store="Safeway")

        result = list_manager.get_list(store="Giant")
        items = result["data"]["list"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Milk"

    def test_filter_by_category(self, list_manager):
        """Filter list by category."""
        list_manager.add_item(name="Milk", category="Dairy")
        list_manager.add_item(name="Apples", category="Produce")

        result = list_manager.get_list(category="Dairy")
        items = result["data"]["list"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Milk"

    def test_filter_by_status(self, list_manager):
        """Filter list by status."""
        result = list_manager.add_item(name="Milk")
        milk_id = result["data"]["item"]["id"]
        list_manager.add_item(name="Bread")

        list_manager.mark_bought(milk_id)

        result = list_manager.get_list(status=ItemStatus.TO_BUY)
        items = result["data"]["list"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Bread"


class TestMarkBought:
    """Tests for marking items as bought."""

    def test_mark_bought(self, list_manager):
        """Mark item as bought."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.mark_bought(item_id)
        assert result["success"] is True
        assert result["data"]["item"]["status"] == "bought"

    def test_mark_bought_with_quantity(self, list_manager):
        """Mark bought with actual quantity."""
        result = list_manager.add_item(name="Milk", quantity=2)
        item_id = result["data"]["item"]["id"]

        result = list_manager.mark_bought(item_id, quantity=3)
        assert result["data"]["item"]["quantity"] == 3

    def test_mark_bought_with_price(self, list_manager):
        """Mark bought with actual price."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.mark_bought(item_id, price=4.99)
        assert result["data"]["item"]["estimated_price"] == 4.99

    def test_mark_bought_nonexistent_raises_error(self, list_manager):
        """Marking non-existent item raises error."""
        with pytest.raises(ItemNotFoundError):
            list_manager.mark_bought(str(uuid4()))


class TestUpdateItem:
    """Tests for updating items."""

    def test_update_name(self, list_manager):
        """Update item name."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(item_id, name="Whole Milk")
        assert result["data"]["item"]["name"] == "Whole Milk"

    def test_update_multiple_fields(self, list_manager):
        """Update multiple fields at once."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(
            item_id,
            quantity=2,
            store="Giant",
            priority=Priority.HIGH,
        )
        item = result["data"]["item"]
        assert item["quantity"] == 2
        assert item["store"] == "Giant"
        assert item["priority"] == "high"

    def test_update_nonexistent_raises_error(self, list_manager):
        """Updating non-existent item raises error."""
        with pytest.raises(ItemNotFoundError):
            list_manager.update_item(str(uuid4()), name="New Name")


class TestClearBought:
    """Tests for clearing bought items."""

    def test_clear_bought(self, list_manager):
        """Clear bought items from list."""
        result = list_manager.add_item(name="Milk")
        milk_id = result["data"]["item"]["id"]
        list_manager.add_item(name="Bread")

        list_manager.mark_bought(milk_id)
        result = list_manager.clear_bought()

        assert result["success"] is True
        assert result["data"]["removed_count"] == 1

        # Verify only Bread remains
        list_result = list_manager.get_list()
        assert len(list_result["data"]["list"]["items"]) == 1
        assert list_result["data"]["list"]["items"][0]["name"] == "Bread"

    def test_clear_bought_empty(self, list_manager):
        """Clear with no bought items."""
        list_manager.add_item(name="Milk")

        result = list_manager.clear_bought()
        assert result["data"]["removed_count"] == 0


class TestGrouping:
    """Tests for grouping items."""

    def test_get_by_store(self, list_manager):
        """Group items by store."""
        list_manager.add_item(name="Milk", store="Giant")
        list_manager.add_item(name="Bread", store="Giant")
        list_manager.add_item(name="Apples", store="Safeway")
        list_manager.add_item(name="Cheese")  # No store

        result = list_manager.get_by_store()
        by_store = result["data"]["by_store"]

        assert len(by_store["Giant"]) == 2
        assert len(by_store["Safeway"]) == 1
        assert len(by_store["Unspecified"]) == 1

    def test_get_by_category(self, list_manager):
        """Group items by category."""
        list_manager.add_item(name="Milk", category="Dairy")
        list_manager.add_item(name="Cheese", category="Dairy")
        list_manager.add_item(name="Apples", category="Produce")

        result = list_manager.get_by_category()
        by_category = result["data"]["by_category"]

        assert len(by_category["Dairy"]) == 2
        assert len(by_category["Produce"]) == 1


class TestGetItem:
    """Tests for getting individual items."""

    def test_get_item(self, list_manager):
        """Get item by ID."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        item = list_manager.get_item(item_id)
        assert item.name == "Milk"

    def test_get_item_not_found(self, list_manager):
        """Get non-existent item raises error."""
        with pytest.raises(ItemNotFoundError):
            list_manager.get_item(str(uuid4()))


class TestUpdateItemFields:
    """Tests for updating individual item fields."""

    def test_update_unit(self, list_manager):
        """Update item unit."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(item_id, unit="gallon")
        assert result["data"]["item"]["unit"] == "gallon"

    def test_update_brand_preference(self, list_manager):
        """Update item brand preference."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(item_id, brand_preference="Horizon")
        assert result["data"]["item"]["brand_preference"] == "Horizon"

    def test_update_estimated_price(self, list_manager):
        """Update item estimated price."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(item_id, estimated_price=4.99)
        assert result["data"]["item"]["estimated_price"] == 4.99

    def test_update_notes(self, list_manager):
        """Update item notes."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(item_id, notes="Whole milk only")
        assert result["data"]["item"]["notes"] == "Whole milk only"

    def test_update_status(self, list_manager):
        """Update item status directly."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(item_id, status=ItemStatus.STILL_NEEDED)
        assert result["data"]["item"]["status"] == "still_needed"

    def test_update_category(self, list_manager):
        """Update item category."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        result = list_manager.update_item(item_id, category="Dairy & Eggs")
        assert result["data"]["item"]["category"] == "Dairy & Eggs"
