"""Tests for Phase 2 CLI commands (stats, out-of-stock)."""

import json
from datetime import date

import pytest
from typer.testing import CliRunner

from grocery_tracker.main import app
from grocery_tracker.models import LineItem, Receipt

runner = CliRunner()


@pytest.fixture(autouse=True)
def _setup_cli(tmp_path, monkeypatch):
    """Set up CLI with temp data directory."""
    import grocery_tracker.main as main_module

    from grocery_tracker.data_store import DataStore
    from grocery_tracker.list_manager import ListManager

    ds = DataStore(data_dir=tmp_path / "data")
    lm = ListManager(data_store=ds)

    main_module.data_store = ds
    main_module.list_manager = lm

    yield ds, lm

    main_module.data_store = None
    main_module.list_manager = None


class TestStatsCommand:
    """Tests for grocery stats command."""

    def test_stats_default_json(self, _setup_cli):
        """Stats command returns spending summary."""
        result = runner.invoke(app, ["--json", "stats"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "spending" in output["data"]
        assert output["data"]["spending"]["period"] == "monthly"

    def test_stats_weekly(self, _setup_cli):
        """Stats command with weekly period."""
        result = runner.invoke(app, ["--json", "stats", "--period", "weekly"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["spending"]["period"] == "weekly"

    def test_stats_with_budget(self, _setup_cli):
        """Stats command with budget."""
        result = runner.invoke(app, ["--json", "stats", "--budget", "500"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["spending"]["budget_limit"] == 500.0

    def test_stats_with_receipt_data(self, _setup_cli):
        """Stats with actual receipt data."""
        ds, _ = _setup_cli
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49),
            ],
            subtotal=5.49,
            total=5.49,
        )
        ds.save_receipt(receipt)

        result = runner.invoke(app, ["--json", "stats"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["spending"]["total_spending"] == 5.49

    def test_stats_rich_mode(self, _setup_cli):
        """Stats command in Rich mode doesn't crash."""
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0


class TestStatsFrequencyCommand:
    """Tests for grocery stats frequency command."""

    def test_frequency_no_data(self, _setup_cli):
        """Frequency command warns when no data."""
        result = runner.invoke(app, ["--json", "stats", "frequency", "Milk"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "warning" in output

    def test_frequency_with_data(self, _setup_cli):
        """Frequency command returns data."""
        ds, _ = _setup_cli
        from grocery_tracker.models import FrequencyData, PurchaseRecord
        from datetime import timedelta

        today = date.today()
        freq = FrequencyData(
            item_name="Milk",
            category="Dairy & Eggs",
            purchase_history=[
                PurchaseRecord(date=today - timedelta(days=10)),
                PurchaseRecord(date=today - timedelta(days=5)),
            ],
        )
        ds.save_frequency_data({"Milk": freq})

        result = runner.invoke(app, ["--json", "stats", "frequency", "Milk"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["frequency"]["item_name"] == "Milk"
        assert output["data"]["frequency"]["average_days"] == 5.0


class TestStatsCompareCommand:
    """Tests for grocery stats compare command."""

    def test_compare_no_data(self, _setup_cli):
        """Compare command warns when no data."""
        result = runner.invoke(app, ["--json", "stats", "compare", "Milk"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "warning" in output

    def test_compare_with_data(self, _setup_cli):
        """Compare command returns price comparison."""
        ds, _ = _setup_cli
        ds.update_price("Milk", "Giant", 5.49, date.today())
        ds.update_price("Milk", "TJ", 4.99, date.today())

        result = runner.invoke(app, ["--json", "stats", "compare", "Milk"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["comparison"]["cheapest_store"] == "TJ"


class TestStatsSuggestCommand:
    """Tests for grocery stats suggest command."""

    def test_suggest_empty(self, _setup_cli):
        """Suggest command with no data."""
        result = runner.invoke(app, ["--json", "stats", "suggest"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["suggestions"] == []

    def test_suggest_with_data(self, _setup_cli):
        """Suggest command finds suggestions."""
        ds, _ = _setup_cli
        from grocery_tracker.models import FrequencyData, PurchaseRecord
        from datetime import timedelta

        today = date.today()
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[
                PurchaseRecord(date=today - timedelta(days=20)),
                PurchaseRecord(date=today - timedelta(days=15)),
                PurchaseRecord(date=today - timedelta(days=10)),
            ],
        )
        ds.save_frequency_data({"Milk": freq})

        result = runner.invoke(app, ["--json", "stats", "suggest"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["suggestions"]) >= 1


class TestOutOfStockReportCommand:
    """Tests for grocery out-of-stock report command."""

    def test_report_basic(self, _setup_cli):
        """Report an item as out of stock."""
        result = runner.invoke(
            app, ["--json", "out-of-stock", "report", "Oat Milk", "Giant"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "record" in output["data"]
        assert output["data"]["record"]["item_name"] == "Oat Milk"
        assert output["data"]["record"]["store"] == "Giant"

    def test_report_with_substitution(self, _setup_cli):
        """Report with substitution."""
        result = runner.invoke(
            app,
            [
                "--json",
                "out-of-stock",
                "report",
                "Oat Milk",
                "Giant",
                "--sub",
                "Almond Milk",
                "--by",
                "Alice",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["record"]["substitution"] == "Almond Milk"
        assert output["data"]["record"]["reported_by"] == "Alice"

    def test_report_rich_mode(self, _setup_cli):
        """Report command in Rich mode doesn't crash."""
        result = runner.invoke(
            app, ["out-of-stock", "report", "Eggs", "Giant"]
        )
        assert result.exit_code == 0


class TestOutOfStockListCommand:
    """Tests for grocery out-of-stock list command."""

    def test_list_empty(self, _setup_cli):
        """List with no records."""
        result = runner.invoke(app, ["--json", "out-of-stock", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["out_of_stock"] == []

    def test_list_with_records(self, _setup_cli):
        """List returns records after reporting."""
        runner.invoke(
            app, ["--json", "out-of-stock", "report", "Oat Milk", "Giant"]
        )
        runner.invoke(
            app, ["--json", "out-of-stock", "report", "Eggs", "TJ"]
        )

        result = runner.invoke(app, ["--json", "out-of-stock", "list"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["out_of_stock"]) == 2

    def test_list_filter_by_item(self, _setup_cli):
        """List filters by item name."""
        runner.invoke(
            app, ["--json", "out-of-stock", "report", "Oat Milk", "Giant"]
        )
        runner.invoke(
            app, ["--json", "out-of-stock", "report", "Eggs", "TJ"]
        )

        result = runner.invoke(
            app, ["--json", "out-of-stock", "list", "--item", "Oat Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["out_of_stock"]) == 1

    def test_list_filter_by_store(self, _setup_cli):
        """List filters by store."""
        runner.invoke(
            app, ["--json", "out-of-stock", "report", "Oat Milk", "Giant"]
        )
        runner.invoke(
            app, ["--json", "out-of-stock", "report", "Eggs", "TJ"]
        )

        result = runner.invoke(
            app, ["--json", "out-of-stock", "list", "--store", "Giant"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["out_of_stock"]) == 1
        assert output["data"]["out_of_stock"][0]["store"] == "Giant"
