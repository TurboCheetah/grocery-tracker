"""Integration tests for complete workflows."""

import json
from datetime import date

import pytest
from typer.testing import CliRunner

from grocery_tracker.data_store import DataStore
from grocery_tracker.list_manager import ListManager
from grocery_tracker.main import app
from grocery_tracker.models import ItemStatus, LineItem
from grocery_tracker.receipt_processor import ReceiptInput, ReceiptProcessor

runner = CliRunner()


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def data_store(temp_data_dir):
    """Create a DataStore with temporary directory."""
    return DataStore(data_dir=temp_data_dir)


@pytest.fixture
def list_manager(data_store):
    """Create a ListManager with temporary storage."""
    return ListManager(data_store=data_store)


@pytest.fixture
def receipt_processor(list_manager, data_store):
    """Create a ReceiptProcessor."""
    return ReceiptProcessor(list_manager=list_manager, data_store=data_store)


class TestShoppingWorkflow:
    """Integration tests for the complete shopping workflow."""

    def test_complete_shopping_trip_programmatic(self, list_manager, receipt_processor, data_store):
        """Test complete shopping workflow using Python API.

        This workflow tests:
        1. Adding items to the list
        2. Processing a receipt
        3. Verifying items are marked as bought
        4. Checking still-needed items
        5. Verifying price history is updated
        """
        # Step 1: Add items to the shopping list
        list_manager.add_item(name="Milk", quantity=2, store="Giant", category="Dairy")
        list_manager.add_item(name="Bread", quantity=1, store="Giant", category="Bakery")
        list_manager.add_item(name="Eggs", quantity=1, store="Giant", category="Dairy")
        list_manager.add_item(name="Apples", quantity=6, store="Giant", category="Produce")

        # Verify list has 4 items
        list_result = list_manager.get_list()
        assert list_result["data"]["list"]["total_items"] == 4

        # Step 2: Go shopping - process a receipt
        receipt_input = ReceiptInput(
            store_name="Giant Food",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Whole Milk 2%", quantity=2, unit_price=4.99, total_price=9.98),
                LineItem(item_name="Wheat Bread", quantity=1, unit_price=3.49, total_price=3.49),
                LineItem(item_name="Gala Apples", quantity=6, unit_price=0.99, total_price=5.94),
                # Impulse buy not on list
                LineItem(item_name="Chocolate Bar", quantity=2, unit_price=1.99, total_price=3.98),
            ],
            subtotal=23.39,
            tax=1.17,
            total=24.56,
        )

        result = receipt_processor.process_receipt(receipt_input)

        # Step 3: Verify reconciliation results
        assert result.matched_items == 3  # Milk, Bread, Apples matched
        assert result.items_purchased == 4
        assert result.total_spent == 24.56
        assert "Eggs" in result.still_needed  # Eggs not bought
        assert "Chocolate Bar" in result.newly_bought  # Impulse buy

        # Step 4: Verify item statuses
        to_buy_result = list_manager.get_list(status=ItemStatus.TO_BUY)
        to_buy_items = to_buy_result["data"]["list"]["items"]
        assert len(to_buy_items) == 1
        assert to_buy_items[0]["name"] == "Eggs"

        bought_result = list_manager.get_list(status=ItemStatus.BOUGHT)
        bought_items = bought_result["data"]["list"]["items"]
        assert len(bought_items) == 3

        # Step 5: Verify price history was updated
        milk_history = data_store.get_price_history("Whole Milk 2%", "Giant Food")
        assert milk_history is not None
        assert milk_history.current_price == 4.99

        # Step 6: Clear bought items
        clear_result = list_manager.clear_bought()
        assert clear_result["data"]["removed_count"] == 3

        # Verify only Eggs remains
        final_list = list_manager.get_list()
        assert final_list["data"]["list"]["total_items"] == 1
        assert final_list["data"]["list"]["items"][0]["name"] == "Eggs"

    def test_complete_shopping_trip_cli(self, temp_data_dir):
        """Test complete shopping workflow using CLI.

        Same workflow as above but using CLI commands.
        """
        # Step 1: Add items to shopping list
        items = [
            ("Milk", "--quantity", "2", "--store", "Giant", "--category", "Dairy"),
            ("Bread", "--store", "Giant", "--category", "Bakery"),
            ("Eggs", "--store", "Giant", "--category", "Dairy"),
        ]

        for item_args in items:
            result = runner.invoke(
                app,
                ["--json", "--data-dir", str(temp_data_dir), "add", *item_args],
            )
            assert result.exit_code == 0

        # Verify list
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "list"])
        data = json.loads(result.stdout)
        assert data["data"]["list"]["total_items"] == 3

        # Step 2: Process receipt
        receipt_data = json.dumps(
            {
                "store_name": "Giant",
                "transaction_date": "2024-01-15",
                "line_items": [
                    {"item_name": "Milk", "quantity": 2, "unit_price": 4.99, "total_price": 9.98},
                    {"item_name": "Bread", "quantity": 1, "unit_price": 3.49, "total_price": 3.49},
                ],
                "subtotal": 13.47,
                "tax": 0.67,
                "total": 14.14,
            }
        )

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "receipt",
                "process",
                "--data",
                receipt_data,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["reconciliation"]["matched_items"] == 2
        assert "Eggs" in data["data"]["reconciliation"]["still_needed"]

        # Step 3: Clear bought items
        result = runner.invoke(
            app, ["--json", "--data-dir", str(temp_data_dir), "clear", "--bought"]
        )
        assert result.exit_code == 0

        # Verify only Eggs remains
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "list"])
        data = json.loads(result.stdout)
        assert data["data"]["list"]["total_items"] == 1
        assert data["data"]["list"]["items"][0]["name"] == "Eggs"


class TestPriceTrackingWorkflow:
    """Integration tests for price tracking workflow."""

    def test_price_tracking_over_time(self, data_store, list_manager, receipt_processor):
        """Test price tracking across multiple shopping trips.

        This workflow tests:
        1. Processing multiple receipts over time
        2. Building price history
        3. Analyzing price trends
        """
        # First shopping trip
        receipt1 = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 1),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )
        receipt_processor.process_receipt(receipt1)

        # Second trip - price went up
        receipt2 = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 8),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49),
            ],
            subtotal=5.49,
            total=5.82,
        )
        receipt_processor.process_receipt(receipt2)

        # Third trip - on sale
        receipt3 = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=3.99, total_price=3.99),
            ],
            subtotal=3.99,
            total=4.23,
        )
        receipt_processor.process_receipt(receipt3)

        # Check price history
        history = data_store.get_price_history("Milk", "Giant")
        assert history is not None
        assert len(history.price_points) == 3

        # Verify price statistics
        assert history.current_price == 3.99  # Most recent
        assert history.lowest_price == 3.99
        assert history.highest_price == 5.49
        assert abs(history.average_price - 4.82) < 0.01

    def test_price_comparison_across_stores(self, data_store, receipt_processor):
        """Test comparing prices across different stores."""
        # Buy from Giant
        receipt1 = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )
        receipt_processor.process_receipt(receipt1)

        # Buy from Safeway
        receipt2 = ReceiptInput(
            store_name="Safeway",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.49, total_price=4.49),
            ],
            subtotal=4.49,
            total=4.76,
        )
        receipt_processor.process_receipt(receipt2)

        # Get combined history
        combined_history = data_store.get_price_history("Milk")
        assert combined_history is not None
        assert len(combined_history.price_points) == 2

        # Get store-specific history
        giant_history = data_store.get_price_history("Milk", "Giant")
        safeway_history = data_store.get_price_history("Milk", "Safeway")

        assert giant_history.current_price == 4.99
        assert safeway_history.current_price == 4.49


class TestMultiUserWorkflow:
    """Integration tests for multi-user scenarios."""

    def test_items_added_by_different_users(self, list_manager):
        """Test tracking which user added each item."""
        # Francisco adds items
        list_manager.add_item(name="Milk", added_by="Francisco")
        list_manager.add_item(name="Coffee", added_by="Francisco")

        # Loki adds items
        list_manager.add_item(name="Cat Food", added_by="Loki")
        list_manager.add_item(name="Tofu", added_by="Loki")

        # Get full list
        result = list_manager.get_list()
        items = result["data"]["list"]["items"]

        francisco_items = [i for i in items if i["added_by"] == "Francisco"]
        loki_items = [i for i in items if i["added_by"] == "Loki"]

        assert len(francisco_items) == 2
        assert len(loki_items) == 2


class TestDataPersistenceWorkflow:
    """Integration tests for data persistence."""

    def test_data_survives_restart(self, temp_data_dir):
        """Test that data persists between sessions."""
        # Session 1: Add items
        store1 = DataStore(data_dir=temp_data_dir)
        manager1 = ListManager(data_store=store1)
        manager1.add_item(name="Milk", quantity=2)
        manager1.add_item(name="Bread")

        # "Restart" - create new instances
        store2 = DataStore(data_dir=temp_data_dir)
        manager2 = ListManager(data_store=store2)

        # Verify data is still there
        result = manager2.get_list()
        assert result["data"]["list"]["total_items"] == 2

        # Modify in session 2
        items = result["data"]["list"]["items"]
        milk_id = next(i["id"] for i in items if i["name"] == "Milk")
        manager2.mark_bought(milk_id)

        # "Restart" again
        store3 = DataStore(data_dir=temp_data_dir)
        manager3 = ListManager(data_store=store3)

        # Verify modification persisted
        result = manager3.get_list(status=ItemStatus.BOUGHT)
        assert len(result["data"]["list"]["items"]) == 1
        assert result["data"]["list"]["items"][0]["name"] == "Milk"
