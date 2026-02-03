"""Tests for Phase 3 analytics: waste logging, waste insights, budget tracking."""

from datetime import date, timedelta

import pytest

from grocery_tracker.analytics import Analytics
from grocery_tracker.models import (
    BudgetTracking,
    CategoryBudget,
    DealType,
    SavingsType,
    WasteReason,
    WasteRecord,
)


@pytest.fixture
def analytics(data_store):
    """Create an Analytics instance with test data store."""
    return Analytics(data_store=data_store)


class TestLogWaste:
    """Tests for waste logging."""

    def test_log_basic(self, analytics):
        """Log a basic waste entry."""
        record = analytics.log_waste(item_name="Milk", reason=WasteReason.SPOILED)
        assert record.item_name == "Milk"
        assert record.reason == WasteReason.SPOILED

    def test_log_with_all_fields(self, analytics):
        """Log waste with all fields."""
        record = analytics.log_waste(
            item_name="Bell Peppers",
            quantity=3.0,
            unit="pieces",
            reason=WasteReason.OVERRIPE,
            estimated_cost=2.97,
            original_purchase_date=date.today() - timedelta(days=5),
            logged_by="Francisco",
        )
        assert record.quantity == 3.0
        assert record.estimated_cost == 2.97
        assert record.logged_by == "Francisco"

    def test_log_persists(self, analytics, data_store):
        """Logged waste records persist."""
        analytics.log_waste(item_name="Bread", reason=WasteReason.NEVER_USED)
        records = data_store.load_waste_log()
        assert len(records) == 1
        assert records[0].item_name == "Bread"


class TestWasteSummary:
    """Tests for waste summary analytics."""

    def test_empty_summary(self, analytics):
        """Empty waste log returns zeroes."""
        summary = analytics.waste_summary()
        assert summary["total_items_wasted"] == 0
        assert summary["total_cost"] == 0.0

    def test_monthly_summary(self, analytics, data_store):
        """Monthly summary counts current month records."""
        data_store.add_waste_record(
            WasteRecord(item_name="Milk", reason=WasteReason.SPOILED, estimated_cost=5.49)
        )
        data_store.add_waste_record(
            WasteRecord(item_name="Bread", reason=WasteReason.NEVER_USED, estimated_cost=3.99)
        )

        summary = analytics.waste_summary(period="monthly")
        assert summary["total_items_wasted"] == 2
        assert summary["total_cost"] == 9.48
        assert summary["by_reason"]["spoiled"] == 1
        assert summary["by_reason"]["never_used"] == 1

    def test_weekly_summary(self, analytics, data_store):
        """Weekly summary uses correct period."""
        data_store.add_waste_record(
            WasteRecord(item_name="Yogurt", reason=WasteReason.SPOILED)
        )
        summary = analytics.waste_summary(period="weekly")
        assert summary["period"] == "weekly"
        assert summary["total_items_wasted"] == 1

    def test_yearly_summary(self, analytics, data_store):
        """Yearly summary uses correct period."""
        data_store.add_waste_record(
            WasteRecord(item_name="Rice", reason=WasteReason.OTHER)
        )
        summary = analytics.waste_summary(period="yearly")
        assert summary["period"] == "yearly"

    def test_most_wasted(self, analytics, data_store):
        """Most wasted items are ranked."""
        for _ in range(3):
            data_store.add_waste_record(
                WasteRecord(item_name="Bananas", reason=WasteReason.OVERRIPE)
            )
        data_store.add_waste_record(
            WasteRecord(item_name="Milk", reason=WasteReason.SPOILED)
        )

        summary = analytics.waste_summary()
        assert summary["most_wasted"][0]["item"] == "Bananas"
        assert summary["most_wasted"][0]["count"] == 3


class TestWasteInsights:
    """Tests for waste reduction insights."""

    def test_no_insights(self, analytics):
        """No insights when no waste data."""
        assert analytics.waste_insights() == []

    def test_frequent_waste_insight(self, analytics, data_store):
        """Generates insight for items wasted 3+ times."""
        for _ in range(3):
            data_store.add_waste_record(
                WasteRecord(
                    item_name="Bell Peppers",
                    reason=WasteReason.SPOILED,
                    estimated_cost=1.50,
                )
            )

        insights = analytics.waste_insights()
        assert any("Bell Peppers" in i and "3 times" in i for i in insights)

    def test_double_waste_insight(self, analytics, data_store):
        """Generates insight for items wasted 2 times."""
        for _ in range(2):
            data_store.add_waste_record(
                WasteRecord(item_name="Avocado", reason=WasteReason.OVERRIPE)
            )

        insights = analytics.waste_insights()
        assert any("Avocado" in i and "2 times" in i for i in insights)

    def test_spoilage_pattern_insight(self, analytics, data_store):
        """Generates insight for frequent spoilage."""
        for _ in range(3):
            data_store.add_waste_record(
                WasteRecord(item_name=f"Item {_}", reason=WasteReason.SPOILED)
            )

        insights = analytics.waste_insights()
        assert any("spoiled" in i.lower() for i in insights)


class TestBudgetTracking:
    """Tests for budget setting and status."""

    def test_set_budget(self, analytics):
        """Set a monthly budget."""
        budget = analytics.set_budget(monthly_limit=500.0)
        assert budget.monthly_limit == 500.0
        assert budget.month == date.today().strftime("%Y-%m")

    def test_set_budget_with_categories(self, analytics):
        """Set budget with category allocations."""
        budget = analytics.set_budget(
            monthly_limit=500.0,
            category_limits={"Produce": 100.0, "Dairy & Eggs": 80.0},
        )
        assert len(budget.category_budgets) == 2
        assert budget.category_budgets[0].category == "Produce"
        assert budget.category_budgets[0].limit == 100.0

    def test_get_budget_status(self, analytics, data_store):
        """Get budget status with spending calculated."""
        analytics.set_budget(monthly_limit=500.0)
        budget = analytics.get_budget_status()
        assert budget is not None
        assert budget.monthly_limit == 500.0

    def test_no_budget_returns_none(self, analytics):
        """Returns None when no budget is set."""
        assert analytics.get_budget_status() is None

    def test_budget_specific_month(self, analytics):
        """Set and retrieve budget for specific month."""
        budget = analytics.set_budget(monthly_limit=600.0, month="2026-02")
        assert budget.month == "2026-02"

        retrieved = analytics.get_budget_status(month="2026-02")
        assert retrieved is not None
        assert retrieved.monthly_limit == 600.0


class TestDealsAndSavings:
    """Tests for deal redemption and savings tracking."""

    def test_add_and_redeem_deal(self, analytics, data_store):
        """Redeeming a deal logs savings and updates deal."""
        deal = analytics.add_deal(
            item_name="Eggs",
            store="Giant",
            deal_type=DealType.SALE,
            regular_price=3.99,
            deal_price=2.99,
        )

        updated, record = analytics.redeem_deal(str(deal.id), quantity=2)

        assert updated.redeemed is True
        assert record.savings_amount == 2.00

        stored = data_store.get_deal(deal.id)
        assert stored is not None
        assert stored.redeemed is True

    def test_log_savings(self, analytics, data_store):
        """Manual savings log persists."""
        record = analytics.log_savings(
            item_name="Milk",
            store="Giant",
            savings_amount=1.50,
            savings_type=SavingsType.COUPON,
        )
        assert record.savings_amount == 1.50

        records = data_store.load_savings()
        assert len(records) == 1
        assert records[0].item_name == "Milk"

    def test_savings_summary(self, analytics):
        """Savings summary aggregates totals."""
        analytics.log_savings(
            item_name="Milk",
            store="Giant",
            savings_amount=2.00,
            savings_type=SavingsType.SALE,
        )
        analytics.log_savings(
            item_name="Eggs",
            store="Giant",
            savings_amount=1.00,
            savings_type=SavingsType.COUPON,
        )

        summary = analytics.savings_summary(period="monthly")
        assert summary.total_savings == 3.00
        assert summary.savings_count == 2
        assert summary.by_type["sale"] == 2.00
