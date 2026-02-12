"""Tests for Phase 2 CLI commands (stats, out-of-stock)."""

import json
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from grocery_tracker.data_store import DataStore
from grocery_tracker.main import app
from grocery_tracker.models import LineItem, OutOfStockRecord, Receipt

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
        from datetime import timedelta

        from grocery_tracker.models import FrequencyData, PurchaseRecord

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
        data_store.update_price("Milk", "Giant", 4.79, date.today() - timedelta(days=40))

        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "compare", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["comparison"]["cheapest_store"] == "TJ"
        assert "average_price_30d" in output["data"]["comparison"]
        assert "average_price_90d" in output["data"]["comparison"]
        assert "delta_vs_30d_pct" in output["data"]["comparison"]
        assert "delta_vs_90d_pct" in output["data"]["comparison"]


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
        from datetime import timedelta

        from grocery_tracker.models import FrequencyData, PurchaseRecord

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

    def test_suggest_includes_seasonal_context(self, cli_data_dir, data_store):
        """Suggest command includes seasonal optimization context when supported."""
        today = date.today()
        year = today.year - 1

        for month in (6, 7):
            for day in (3, 10, 17, 24):
                data_store.update_price("Strawberries", "Giant", 3.00, date(year, month, day))

        for month in (1, 2):
            for day in (5, 19):
                data_store.update_price("Strawberries", "Giant", 6.00, date(year, month, day))

        data_store.update_price("Strawberries", "Giant", 6.80, today)

        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats", "suggest"])
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        seasonal = [
            s for s in output["data"]["suggestions"] if s["type"] == "seasonal_optimization"
        ]
        assert len(seasonal) == 1
        assert "baseline" in seasonal[0]["data"]
        assert "current_context" in seasonal[0]["data"]
        assert "recommendation_reason" in seasonal[0]["data"]


class TestStatsRecommendCommand:
    """Tests for grocery stats recommend command."""

    def test_recommend_no_data(self, cli_data_dir):
        """Recommend command warns when no data exists."""
        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "recommend", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "warning" in output

    def test_recommend_with_data(self, cli_data_dir, data_store):
        """Recommend command returns ranked recommendation data."""
        today = date.today()
        data_store.update_price("Milk", "Giant", 5.49, today - timedelta(days=1))
        data_store.update_price("Milk", "Giant", 5.39, today - timedelta(days=10))
        data_store.update_price("Milk", "TJ", 4.99, today - timedelta(days=2))
        data_store.update_price("Milk", "TJ", 5.09, today - timedelta(days=12))
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Milk", store="Giant", substitution="Oat Milk")
        )

        result = runner.invoke(
            app, ["--json", "--data-dir", str(cli_data_dir), "stats", "recommend", "Milk"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        recommendation = output["data"]["recommendation"]
        assert recommendation["item_name"] == "Milk"
        assert recommendation["recommended_store"] == "TJ"
        assert recommendation["confidence"] in {"medium", "high"}
        assert len(recommendation["ranked_stores"]) >= 2

    def test_recommend_rich_mode(self, cli_data_dir, data_store):
        """Recommend command in Rich mode doesn't crash."""
        today = date.today()
        data_store.update_price("Milk", "Giant", 5.49, today - timedelta(days=1))
        data_store.update_price("Milk", "TJ", 4.99, today - timedelta(days=2))

        result = runner.invoke(app, ["--data-dir", str(cli_data_dir), "stats", "recommend", "Milk"])
        assert result.exit_code == 0


class TestStatsRouteCommand:
    """Tests for grocery stats route command."""

    def test_route_no_pending_items(self, cli_data_dir):
        """Route command warns when list has no pending items."""
        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats", "route"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "warning" in output

    def test_route_with_items(self, cli_data_dir, data_store):
        """Route command returns deterministic route data."""
        today = date.today()
        data_store.update_price("Milk", "TJ", 4.79, today - timedelta(days=1))
        data_store.update_price("Milk", "TJ", 4.89, today - timedelta(days=8))
        data_store.update_price("Milk", "Giant", 5.29, today - timedelta(days=2))
        data_store.update_price("Milk", "Giant", 5.19, today - timedelta(days=7))

        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "add",
                "Milk",
            ],
        )

        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats", "route"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["route"]["total_items"] == 1
        assert len(output["data"]["route"]["stops"]) >= 1

    def test_route_rich_mode(self, cli_data_dir):
        """Route command in Rich mode doesn't crash."""
        runner.invoke(app, ["--data-dir", str(cli_data_dir), "add", "Bread", "--store", "Giant"])
        result = runner.invoke(app, ["--data-dir", str(cli_data_dir), "stats", "route"])
        assert result.exit_code == 0


class TestStatsSavingsCommand:
    """Tests for grocery stats savings command."""

    def test_savings_empty(self, cli_data_dir):
        """Savings command returns empty summary when no records exist."""
        result = runner.invoke(app, ["--json", "--data-dir", str(cli_data_dir), "stats", "savings"])
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["data"]["savings"]["total_savings"] == 0.0

    def test_savings_with_receipt_discounts(self, cli_data_dir):
        """Savings command reports totals after processing discounted receipt."""
        receipt_data = json.dumps(
            {
                "store_name": "Giant",
                "transaction_date": date.today().isoformat(),
                "line_items": [
                    {
                        "item_name": "Milk",
                        "quantity": 1,
                        "unit_price": 4.99,
                        "total_price": 4.99,
                        "discount_amount": 1.0,
                    },
                    {
                        "item_name": "Bread",
                        "quantity": 1,
                        "unit_price": 3.99,
                        "total_price": 3.99,
                    },
                ],
                "subtotal": 8.98,
                "discount_total": 0.5,
                "coupon_total": 0.5,
                "total": 8.98,
            }
        )
        process_result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(cli_data_dir),
                "receipt",
                "process",
                "--data",
                receipt_data,
            ],
        )
        assert process_result.exit_code == 0

        result = runner.invoke(
            app,
            ["--json", "--data-dir", str(cli_data_dir), "stats", "savings", "--period", "monthly"],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["savings"]["total_savings"] == 2.0
        assert output["data"]["savings"]["receipt_count"] == 1
        assert len(output["data"]["savings"]["top_items"]) >= 1

    def test_savings_rich_mode_renders_summary(self, cli_data_dir):
        """Savings command in Rich mode renders summary details."""
        result = runner.invoke(app, ["--data-dir", str(cli_data_dir), "stats", "savings"])
        assert result.exit_code == 0
        assert "Savings Summary" in result.stdout


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
                "Alice",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["data"]["record"]["substitution"] == "Almond Milk"
        assert output["data"]["record"]["reported_by"] == "Alice"

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
