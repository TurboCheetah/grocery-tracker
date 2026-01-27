"""Tests for data persistence layer."""

import json
from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from grocery_tracker.data_store import DataStore, JSONEncoder
from grocery_tracker.models import (
    GroceryItem,
    GroceryList,
    LineItem,
    Receipt,
)


@pytest.fixture
def data_store(temp_data_dir):
    """Create a DataStore with temporary directory."""
    return DataStore(data_dir=temp_data_dir)


class TestJSONEncoder:
    """Tests for custom JSON encoder."""

    def test_encode_uuid(self):
        """UUID is encoded as string."""
        test_uuid = uuid4()
        encoded = json.dumps({"id": test_uuid}, cls=JSONEncoder)
        assert str(test_uuid) in encoded

    def test_encode_datetime(self):
        """Datetime is encoded as ISO format."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        encoded = json.dumps({"time": dt}, cls=JSONEncoder)
        assert "2024-01-15T10:30:00" in encoded

    def test_encode_date(self):
        """Date is encoded as ISO format."""
        d = date(2024, 1, 15)
        encoded = json.dumps({"date": d}, cls=JSONEncoder)
        assert "2024-01-15" in encoded

    def test_encode_time(self):
        """Time is encoded as ISO format."""
        from datetime import time

        t = time(14, 30)
        encoded = json.dumps({"time": t}, cls=JSONEncoder)
        assert "14:30" in encoded

    def test_encode_fallback_raises(self):
        """Unsupported types fall through to default encoder."""
        with pytest.raises(TypeError):
            json.dumps({"bad": object()}, cls=JSONEncoder)


class TestDataStoreInit:
    """Tests for DataStore initialization."""

    def test_creates_directories(self, temp_data_dir):
        """DataStore creates required directories."""
        DataStore(data_dir=temp_data_dir)
        assert (temp_data_dir / "receipts").exists()
        assert (temp_data_dir / "receipt_images").exists()

    def test_default_data_dir(self, monkeypatch, tmp_path):
        """DataStore uses ./data by default."""
        monkeypatch.chdir(tmp_path)
        store = DataStore()
        assert store.data_dir == tmp_path / "data"


class TestGroceryListPersistence:
    """Tests for grocery list save/load."""

    def test_load_empty_list(self, data_store):
        """Loading non-existent list returns empty GroceryList."""
        grocery_list = data_store.load_list()
        assert isinstance(grocery_list, GroceryList)
        assert grocery_list.items == []

    def test_save_and_load_list(self, data_store):
        """Saved list can be loaded back."""
        grocery_list = GroceryList(
            items=[
                GroceryItem(name="Milk", quantity=2, store="Giant"),
                GroceryItem(name="Bread", quantity=1),
            ]
        )
        data_store.save_list(grocery_list)

        loaded = data_store.load_list()
        assert len(loaded.items) == 2
        assert loaded.items[0].name == "Milk"
        assert loaded.items[0].quantity == 2
        assert loaded.items[0].store == "Giant"

    def test_save_updates_timestamp(self, data_store):
        """Saving list updates last_updated timestamp."""
        grocery_list = GroceryList()
        old_time = grocery_list.last_updated

        # Small delay to ensure timestamp changes
        import time

        time.sleep(0.01)

        data_store.save_list(grocery_list)
        loaded = data_store.load_list()
        assert loaded.last_updated >= old_time

    def test_get_item_by_id(self, data_store):
        """Can retrieve item by ID."""
        item = GroceryItem(name="Test Item")
        grocery_list = GroceryList(items=[item])
        data_store.save_list(grocery_list)

        found = data_store.get_item(item.id)
        assert found is not None
        assert found.name == "Test Item"

    def test_get_item_not_found(self, data_store):
        """Returns None for non-existent item."""
        found = data_store.get_item(uuid4())
        assert found is None


class TestReceiptPersistence:
    """Tests for receipt save/load."""

    def test_save_and_load_receipt(self, data_store):
        """Saved receipt can be loaded back."""
        receipt = Receipt(
            store_name="Giant Food",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )
        receipt_id = data_store.save_receipt(receipt)

        loaded = data_store.load_receipt(receipt_id)
        assert loaded is not None
        assert loaded.store_name == "Giant Food"
        assert len(loaded.line_items) == 1

    def test_load_nonexistent_receipt(self, data_store):
        """Returns None for non-existent receipt."""
        loaded = data_store.load_receipt(uuid4())
        assert loaded is None

    def test_list_receipts(self, data_store):
        """Can list all receipts."""
        # Save multiple receipts
        for i in range(3):
            receipt = Receipt(
                store_name=f"Store {i}",
                transaction_date=date(2024, 1, 10 + i),
                line_items=[
                    LineItem(item_name="Item", quantity=1, unit_price=1.0, total_price=1.0)
                ],
                subtotal=1.0,
                total=1.0,
            )
            data_store.save_receipt(receipt)

        receipts = data_store.list_receipts()
        assert len(receipts) == 3
        # Should be sorted by date descending
        assert receipts[0].transaction_date > receipts[-1].transaction_date


class TestPriceHistoryPersistence:
    """Tests for price history save/load."""

    def test_load_empty_history(self, data_store):
        """Loading non-existent history returns empty dict."""
        history = data_store.load_price_history()
        assert history == {}

    def test_update_and_load_price(self, data_store):
        """Can update and retrieve price history."""
        data_store.update_price(
            item_name="Milk",
            store="Giant",
            price=4.99,
            purchase_date=date(2024, 1, 15),
        )

        history = data_store.load_price_history()
        assert "Milk" in history
        assert "Giant" in history["Milk"]
        assert len(history["Milk"]["Giant"].price_points) == 1
        assert history["Milk"]["Giant"].price_points[0].price == 4.99

    def test_multiple_price_points(self, data_store):
        """Multiple prices for same item accumulate."""
        data_store.update_price("Milk", "Giant", 4.99, date(2024, 1, 10))
        data_store.update_price("Milk", "Giant", 5.49, date(2024, 1, 15))
        data_store.update_price("Milk", "Safeway", 4.79, date(2024, 1, 12))

        history = data_store.load_price_history()
        assert len(history["Milk"]["Giant"].price_points) == 2
        assert len(history["Milk"]["Safeway"].price_points) == 1

    def test_get_price_history_by_item(self, data_store):
        """Can get price history for specific item."""
        data_store.update_price("Milk", "Giant", 4.99, date(2024, 1, 15))

        history = data_store.get_price_history("Milk", "Giant")
        assert history is not None
        assert history.item_name == "Milk"
        assert history.store == "Giant"

    def test_get_price_history_all_stores(self, data_store):
        """Can get combined price history across stores."""
        data_store.update_price("Milk", "Giant", 4.99, date(2024, 1, 10))
        data_store.update_price("Milk", "Safeway", 4.79, date(2024, 1, 12))

        history = data_store.get_price_history("Milk")
        assert history is not None
        assert len(history.price_points) == 2

    def test_get_price_history_not_found(self, data_store):
        """Returns None for item with no history."""
        history = data_store.get_price_history("NonExistent")
        assert history is None

    def test_get_price_history_all_stores_empty_points(self, data_store):
        """Returns None when all stores have empty price points."""
        from grocery_tracker.models import PriceHistory

        # Manually save history with empty price points
        history = {"Milk": {"Giant": PriceHistory(item_name="Milk", store="Giant")}}
        data_store.save_price_history(history)

        result = data_store.get_price_history("Milk")
        assert result is None

    def test_get_price_history_specific_store_not_found(self, data_store):
        """Returns None when store has no history for item."""
        data_store.update_price("Milk", "Giant", 4.99, date(2024, 1, 15))

        history = data_store.get_price_history("Milk", "Safeway")
        assert history is None

    def test_update_price_with_receipt_id(self, data_store):
        """Price update with receipt ID."""
        receipt_id = uuid4()
        data_store.update_price(
            "Milk",
            "Giant",
            4.99,
            date(2024, 1, 15),
            receipt_id=receipt_id,
            sale=True,
        )

        history = data_store.load_price_history()
        point = history["Milk"]["Giant"].price_points[0]
        assert point.receipt_id == receipt_id
        assert point.sale is True


class TestJSONDecoder:
    """Tests for JSON decoder hook."""

    def test_decode_receipt_with_time(self, data_store):
        """Receipt with transaction_time decodes correctly."""
        from datetime import time

        receipt = Receipt(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            transaction_time=time(14, 30),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=4.99,
        )
        data_store.save_receipt(receipt)

        loaded = data_store.load_receipt(receipt.id)
        assert loaded is not None
        assert loaded.transaction_time == time(14, 30)

    def test_decode_list_with_all_fields(self, data_store):
        """List with all date fields decodes correctly."""
        item = GroceryItem(name="Milk", quantity=1, store="Giant")
        grocery_list = GroceryList(items=[item])
        data_store.save_list(grocery_list)

        loaded = data_store.load_list()
        assert loaded.items[0].added_at is not None
        assert loaded.last_updated is not None

    def test_decoder_invalid_uuid(self):
        """Invalid UUID string stays as string."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"id": "not-a-valid-uuid"})
        assert result["id"] == "not-a-valid-uuid"

    def test_decoder_invalid_datetime(self):
        """Invalid datetime string stays as string."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"added_at": "not-a-datetime"})
        assert result["added_at"] == "not-a-datetime"

    def test_decoder_invalid_date(self):
        """Invalid date string stays as string."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"transaction_date": "not-a-date"})
        assert result["transaction_date"] == "not-a-date"

    def test_decoder_invalid_time(self):
        """Invalid time string stays as string."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"transaction_time": "not-a-time"})
        assert result["transaction_time"] == "not-a-time"

    def test_decoder_valid_uuid(self):
        """Valid UUID string is parsed."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"id": "550e8400-e29b-41d4-a716-446655440000"})
        assert isinstance(result["id"], UUID)

    def test_decoder_valid_datetime(self):
        """Valid datetime string is parsed."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"added_at": "2024-01-15T10:30:00"})
        assert isinstance(result["added_at"], datetime)

    def test_decoder_valid_date(self):
        """Valid date string is parsed."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"transaction_date": "2024-01-15"})
        assert isinstance(result["transaction_date"], date)

    def test_decoder_valid_time(self):
        """Valid time string is parsed."""
        from grocery_tracker.data_store import json_decoder

        result = json_decoder({"transaction_time": "14:30:00"})
        from datetime import time

        assert isinstance(result["transaction_time"], time)
