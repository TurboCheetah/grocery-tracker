"""Tests for Phase 3 CLI commands (inventory, waste, budget, preferences)."""

import json
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from grocery_tracker.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _setup_cli(tmp_path, monkeypatch):
    """Set up CLI with temp data directory."""
    import grocery_tracker.main as main_module

    from grocery_tracker.data_store import DataStore
    from grocery_tracker.inventory_manager import InventoryManager
    from grocery_tracker.list_manager import ListManager

    ds = DataStore(data_dir=tmp_path / "data")
    lm = ListManager(data_store=ds)
    im = InventoryManager(data_store=ds)

    main_module.data_store = ds
    main_module.list_manager = lm
    main_module.inventory_manager = im

    yield ds, lm, im

    main_module.data_store = None
    main_module.list_manager = None
    main_module.inventory_manager = None


# --- Inventory Commands ---


class TestInventoryAdd:
    """Tests for inventory add command."""

    def test_add_basic(self, _setup_cli):
        """Add a basic inventory item."""
        result = runner.invoke(app, ["--json", "inventory", "add", "Milk"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["inventory_item"]["item_name"] == "Milk"

    def test_add_with_options(self, _setup_cli):
        """Add with all options."""
        result = runner.invoke(
            app,
            [
                "--json", "inventory", "add", "Yogurt",
                "--quantity", "3",
                "--unit", "cups",
                "--category", "Dairy & Eggs",
                "--location", "fridge",
                "--threshold", "2",
                "--by", "Alice",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["inventory_item"]["quantity"] == 3.0
        assert output["data"]["inventory_item"]["location"] == "fridge"

    def test_add_with_expiration(self, _setup_cli):
        """Add with expiration date."""
        exp = (date.today() + timedelta(days=7)).isoformat()
        result = runner.invoke(
            app,
            ["--json", "inventory", "add", "Milk", "--expires", exp],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["inventory_item"]["expiration_date"] == exp

    def test_add_rich_mode(self, _setup_cli):
        """Add in Rich mode doesn't crash."""
        result = runner.invoke(app, ["inventory", "add", "Rice"])
        assert result.exit_code == 0


class TestInventoryRemove:
    """Tests for inventory remove command."""

    def test_remove(self, _setup_cli):
        """Remove an inventory item."""
        result = runner.invoke(app, ["--json", "inventory", "add", "Milk"])
        item_id = json.loads(result.stdout)["data"]["inventory_item"]["id"]

        result = runner.invoke(app, ["--json", "inventory", "remove", item_id])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True

    def test_remove_not_found(self, _setup_cli):
        """Remove nonexistent item fails."""
        result = runner.invoke(
            app, ["--json", "inventory", "remove", "00000000-0000-0000-0000-000000000000"]
        )
        assert result.exit_code == 1


class TestInventoryList:
    """Tests for inventory list command."""

    def test_list_empty(self, _setup_cli):
        """Empty inventory."""
        result = runner.invoke(app, ["--json", "inventory", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["inventory"] == []

    def test_list_with_items(self, _setup_cli):
        """List with items."""
        runner.invoke(app, ["--json", "inventory", "add", "Milk"])
        runner.invoke(app, ["--json", "inventory", "add", "Rice"])

        result = runner.invoke(app, ["--json", "inventory", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["count"] == 2

    def test_list_filter_location(self, _setup_cli):
        """Filter by location."""
        runner.invoke(app, ["--json", "inventory", "add", "Milk", "--location", "fridge"])
        runner.invoke(app, ["--json", "inventory", "add", "Rice", "--location", "pantry"])

        result = runner.invoke(
            app, ["--json", "inventory", "list", "--location", "fridge"]
        )
        output = json.loads(result.stdout)
        assert output["data"]["count"] == 1

    def test_list_rich_mode(self, _setup_cli):
        """List in Rich mode doesn't crash."""
        runner.invoke(app, ["inventory", "add", "Milk"])
        result = runner.invoke(app, ["inventory", "list"])
        assert result.exit_code == 0


class TestInventoryExpiring:
    """Tests for expiring command."""

    def test_expiring_empty(self, _setup_cli):
        """No expiring items."""
        result = runner.invoke(app, ["--json", "inventory", "expiring"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["expiring"] == []

    def test_expiring_with_items(self, _setup_cli):
        """Items expiring soon show up."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        runner.invoke(
            app, ["--json", "inventory", "add", "Milk", "--expires", tomorrow]
        )
        result = runner.invoke(app, ["--json", "inventory", "expiring", "--days", "3"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["count"] == 1

    def test_expiring_rich_mode(self, _setup_cli):
        """Expiring in Rich mode."""
        result = runner.invoke(app, ["inventory", "expiring"])
        assert result.exit_code == 0


class TestInventoryLowStock:
    """Tests for low-stock command."""

    def test_low_stock_empty(self, _setup_cli):
        """No low stock items."""
        result = runner.invoke(app, ["--json", "inventory", "low-stock"])
        assert result.exit_code == 0

    def test_low_stock_with_items(self, _setup_cli):
        """Low stock items show up."""
        runner.invoke(
            app,
            ["--json", "inventory", "add", "Eggs", "--quantity", "1", "--threshold", "3"],
        )
        result = runner.invoke(app, ["--json", "inventory", "low-stock"])
        output = json.loads(result.stdout)
        assert output["data"]["count"] == 1

    def test_low_stock_rich_mode(self, _setup_cli):
        """Low stock in Rich mode."""
        result = runner.invoke(app, ["inventory", "low-stock"])
        assert result.exit_code == 0


class TestInventoryUse:
    """Tests for inventory use command."""

    def test_use_item(self, _setup_cli):
        """Use/consume an inventory item."""
        result = runner.invoke(
            app, ["--json", "inventory", "add", "Eggs", "--quantity", "12"]
        )
        item_id = json.loads(result.stdout)["data"]["inventory_item"]["id"]

        result = runner.invoke(
            app, ["--json", "inventory", "use", item_id, "--quantity", "4"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["inventory_item"]["quantity"] == 8.0


# --- Waste Commands ---


class TestWasteLog:
    """Tests for waste log command."""

    def test_log_basic(self, _setup_cli):
        """Log a basic waste entry."""
        result = runner.invoke(
            app, ["--json", "waste", "log", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["record"]["item_name"] == "Milk"

    def test_log_with_options(self, _setup_cli):
        """Log with reason and cost."""
        result = runner.invoke(
            app,
            [
                "--json", "waste", "log", "Bread",
                "--reason", "spoiled",
                "--cost", "3.99",
                "--by", "Bob",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["record"]["reason"] == "spoiled"
        assert output["data"]["record"]["estimated_cost"] == 3.99

    def test_log_rich_mode(self, _setup_cli):
        """Log in Rich mode."""
        result = runner.invoke(app, ["waste", "log", "Bananas"])
        assert result.exit_code == 0


class TestWasteList:
    """Tests for waste list command."""

    def test_list_empty(self, _setup_cli):
        """Empty waste log."""
        result = runner.invoke(app, ["--json", "waste", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["waste_log"] == []

    def test_list_with_records(self, _setup_cli):
        """List with records."""
        runner.invoke(app, ["--json", "waste", "log", "Milk"])
        runner.invoke(app, ["--json", "waste", "log", "Bread"])

        result = runner.invoke(app, ["--json", "waste", "list"])
        output = json.loads(result.stdout)
        assert output["data"]["count"] == 2

    def test_list_filter_item(self, _setup_cli):
        """Filter by item."""
        runner.invoke(app, ["--json", "waste", "log", "Milk"])
        runner.invoke(app, ["--json", "waste", "log", "Bread"])

        result = runner.invoke(
            app, ["--json", "waste", "list", "--item", "Milk"]
        )
        output = json.loads(result.stdout)
        assert output["data"]["count"] == 1

    def test_list_filter_reason(self, _setup_cli):
        """Filter by reason."""
        runner.invoke(
            app, ["--json", "waste", "log", "Milk", "--reason", "spoiled"]
        )
        runner.invoke(
            app, ["--json", "waste", "log", "Bread", "--reason", "never_used"]
        )

        result = runner.invoke(
            app, ["--json", "waste", "list", "--reason", "spoiled"]
        )
        output = json.loads(result.stdout)
        assert output["data"]["count"] == 1

    def test_list_rich_mode(self, _setup_cli):
        """List in Rich mode."""
        result = runner.invoke(app, ["waste", "list"])
        assert result.exit_code == 0


class TestWasteSummary:
    """Tests for waste summary command."""

    def test_summary_empty(self, _setup_cli):
        """Summary with no waste data."""
        result = runner.invoke(app, ["--json", "waste", "summary"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["waste_summary"]["total_items_wasted"] == 0

    def test_summary_with_data(self, _setup_cli):
        """Summary with waste data."""
        runner.invoke(
            app, ["--json", "waste", "log", "Milk", "--cost", "5.49", "--reason", "spoiled"]
        )
        result = runner.invoke(app, ["--json", "waste", "summary"])
        output = json.loads(result.stdout)
        assert output["data"]["waste_summary"]["total_items_wasted"] == 1
        assert output["data"]["waste_summary"]["total_cost"] == 5.49

    def test_summary_rich_mode(self, _setup_cli):
        """Summary in Rich mode."""
        result = runner.invoke(app, ["waste", "summary"])
        assert result.exit_code == 0


# --- Budget Commands ---


class TestBudgetSet:
    """Tests for budget set command."""

    def test_set_budget(self, _setup_cli):
        """Set a monthly budget."""
        result = runner.invoke(app, ["--json", "budget", "set", "500"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["budget"]["monthly_limit"] == 500.0

    def test_set_rich_mode(self, _setup_cli):
        """Set in Rich mode."""
        result = runner.invoke(app, ["budget", "set", "500"])
        assert result.exit_code == 0


class TestBudgetStatus:
    """Tests for budget status command."""

    def test_status_no_budget(self, _setup_cli):
        """Status with no budget set."""
        result = runner.invoke(app, ["--json", "budget", "status"])
        assert result.exit_code == 0  # warns, doesn't fail

    def test_status_with_budget(self, _setup_cli):
        """Status with budget set."""
        runner.invoke(app, ["--json", "budget", "set", "500"])
        result = runner.invoke(app, ["--json", "budget", "status"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["budget_status"]["monthly_limit"] == 500.0

    def test_status_rich_mode(self, _setup_cli):
        """Status in Rich mode."""
        runner.invoke(app, ["budget", "set", "500"])
        result = runner.invoke(app, ["budget", "status"])
        assert result.exit_code == 0


# --- Preferences Commands ---


class TestPreferencesView:
    """Tests for preferences view command."""

    def test_view_no_prefs(self, _setup_cli):
        """View with no preferences set."""
        result = runner.invoke(app, ["--json", "preferences", "view", "Alice"])
        assert result.exit_code == 0  # warns, doesn't fail

    def test_view_with_prefs(self, _setup_cli):
        """View after setting preferences."""
        runner.invoke(
            app,
            ["--json", "preferences", "set", "Alice", "--favorite", "mango"],
        )
        result = runner.invoke(
            app, ["--json", "preferences", "view", "Alice"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["preferences"]["user"] == "Alice"
        assert "mango" in output["data"]["preferences"]["favorite_items"]

    def test_view_rich_mode(self, _setup_cli):
        """View in Rich mode."""
        runner.invoke(
            app,
            ["preferences", "set", "Alice", "--favorite", "mango"],
        )
        result = runner.invoke(app, ["preferences", "view", "Alice"])
        assert result.exit_code == 0


class TestPreferencesSet:
    """Tests for preferences set command."""

    def test_set_brand(self, _setup_cli):
        """Set brand preference."""
        result = runner.invoke(
            app,
            ["--json", "preferences", "set", "Alice", "--brand", "milk:Organic Valley"],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["preferences"]["brand_preferences"]["milk"] == "Organic Valley"

    def test_set_dietary(self, _setup_cli):
        """Set dietary restriction."""
        result = runner.invoke(
            app,
            ["--json", "preferences", "set", "Bob", "--dietary", "vegetarian"],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "vegetarian" in output["data"]["preferences"]["dietary_restrictions"]

    def test_set_allergen(self, _setup_cli):
        """Set allergen."""
        result = runner.invoke(
            app,
            ["--json", "preferences", "set", "Alice", "--allergen", "peanuts"],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "peanuts" in output["data"]["preferences"]["allergens"]

    def test_set_multiple(self, _setup_cli):
        """Set multiple preferences at once."""
        result = runner.invoke(
            app,
            [
                "--json", "preferences", "set", "Alice",
                "--favorite", "mango",
                "--favorite", "dark chocolate",
                "--dietary", "lactose_intolerant",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["preferences"]["favorite_items"]) == 2

    def test_set_rich_mode(self, _setup_cli):
        """Set in Rich mode."""
        result = runner.invoke(
            app,
            ["preferences", "set", "Alice", "--favorite", "mango"],
        )
        assert result.exit_code == 0

    def test_set_updates_existing(self, _setup_cli):
        """Setting preferences updates existing ones."""
        runner.invoke(
            app,
            ["--json", "preferences", "set", "Alice", "--favorite", "mango"],
        )
        runner.invoke(
            app,
            ["--json", "preferences", "set", "Alice", "--dietary", "vegetarian"],
        )

        result = runner.invoke(
            app, ["--json", "preferences", "view", "Alice"]
        )
        output = json.loads(result.stdout)
        assert "mango" in output["data"]["preferences"]["favorite_items"]
        assert "vegetarian" in output["data"]["preferences"]["dietary_restrictions"]
