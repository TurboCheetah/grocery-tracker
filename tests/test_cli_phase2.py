"""Tests for Phase 2 CLI commands (stats, out-of-stock)."""

import json
from datetime import date

import pytest
from typer.testing import CliRunner

from grocery_tracker.main import app
from grocery_tracker.models import LineItem, Receipt
from grocery_tracker.data_store import DataStore

runner = CliRunner()


@pytest.fixture
def cli_data_dir(tmp_path):
    """Create a temp data directory for CLI tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def data_store(cli_data_dir):
    """Create a DataStore for direct data manipulation in tests."""
    return DataStore(data_dir=cli_data_dir)


class TestStatsCommand:
    """Tests for grocery stats command."""

    def test_stats_default_json(self, cli_data_dir):
        """Stats command returns spending summary."""
        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "spending" in output["data"]
        assert output["data"]["spending"]["period"] == "monthly"

    def test_stats_weekly(self, cli_data_dir):
        """Stats command with weekly period."""
        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "--period", "weekly"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["spending"]["period"] == "weekly"

    def test_stats_with_budget(self, cli_data_dir):
        """Stats command with budget."""
        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "--budget", "500"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["spending"]["budget_limit"] == 500.0

    def test_stats_with_receipt_data(self, cli_data_dir, data_store):
        """Stats with actual receipt data."""
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
        data_store.save_receipt(receipt)

        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["spending"]["total_spending"] == 5.49

    def test_stats_rich_mode(self, cli_data_dir):
        """Stats command in Rich mode doesn't crash."""
        result = runner.invoke(app, ["--data-dir", str(cli_data_dir), "stats"])
        assert result.exit_code == 0


class TestStatsFrequencyCommand:
    """Tests for grocery stats frequency command."""

    def test_frequency_no_data(self, cli_data_dir):
        """Frequency command warns when no data."""
        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "frequency", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "warning" in output

    def test_frequency_with_data(self, cli_data_dir, data_store):
        """Frequency command returns data."""
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
        data_store.save_frequency_data({"Milk": freq})

        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "frequency", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["frequency"]["item_name"] == "Milk"
        assert output["data"]["frequency"]["average_days"] == 5.0


class TestStatsCompareCommand:
    """Tests for grocery stats compare command."""

    def test_compare_no_data(self, cli_data_dir):
        """Compare command warns when no data."""
        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "compare", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "warning" in output

    def test_compare_with_data(self, cli_data_dir, data_store):
        """Compare command returns price comparison."""
        data_store.update_price("Milk", "Giant", 5.49, date.today())
        data_store.update_price("Milk", "TJ", 4.99, date.today())

        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "compare", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["comparison"]["cheapest_store"] == "TJ"


class TestStatsSuggestCommand:
    """Tests for grocery stats suggest command."""

    def test_suggest_empty(self, cli_data_dir):
        """Suggest command with no data."""
        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats", "suggest"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["suggestions"] == []

    def test_suggest_with_data(self, cli_data_dir, data_store):
        """Suggest command finds suggestions."""
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
        data_store.save_frequency_data({"Milk": freq})

        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats", "suggest"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["suggestions"]) >= 1


class TestOutOfStockReportCommand:
    """Tests for grocery out-of-stock report command."""

    def test_report_basic(self, cli_data_dir):
        """Report an item as out of stock."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "out-of-stock",
                "report",
                "Oat Milk",
                "Giant",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "record" in output["data"]
        assert output["data"]["record"]["item_name"] == "Oat Milk"
        assert output["data"]["record"]["store"] == "Giant"

    def test_report_with_substitution(self, cli_data_dir):
        """Report with substitution."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "out-of-stock",
                "report",
                "Oat Milk",
                "Giant",
                "--sub",
                "Almond Milk",
                "--by",
                "Francisco",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["record"]["substitution"] == "Almond Milk"
        assert output["data"]["record"]["reported_by"] == "Francisco"

    def test_report_rich_mode(self, cli_data_dir):
        """Report command in Rich mode doesn't crash."""
        result = runner.invoke(
            app, ["--data-dir", str(cli_data_dir), "out-of-stock", "report", "Eggs", "Giant"]
        )
        assert result.exit_code == 0


class TestOutOfStockListCommand:
    """Tests for grocery out-of-stock list command."""

    def test_list_empty(self, cli_data_dir):
        """List with no records."""
        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "out-of-stock", "list"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["out_of_stock"] == []

    def test_list_with_records(self, cli_data_dir):
        """List returns records after reporting."""
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "out-of-stock",
                "report",
                "Oat Milk",
                "Giant",
            ],
        )
        runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "out-of-stock", "report", "Eggs", "TJ"]
        )

        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "out-of-stock", "list"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["out_of_stock"]) == 2

    def test_list_filter_by_item(self, cli_data_dir):
        """List filters by item name."""
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "out-of-stock",
                "report",
                "Oat Milk",
                "Giant",
            ],
        )
        runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "out-of-stock", "report", "Eggs", "TJ"]
        )

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "out-of-stock",
                "list",
                "--item",
                "Oat Milk",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["out_of_stock"]) == 1

    def test_list_filter_by_store(self, cli_data_dir):
        """List filters by store."""
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "out-of-stock",
                "report",
                "Oat Milk",
                "Giant",
            ],
        )
        runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "out-of-stock", "report", "Eggs", "TJ"]
        )

        result = runner.invoke(
            app,
            ["--json", "--data-dir", str(cli_data_dir), "out-of-stock", "list", "--store", "Giant"],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output["data"]["out_of_stock"]) == 1
        assert output["data"]["out_of_stock"][0]["store"] == "Giant"
