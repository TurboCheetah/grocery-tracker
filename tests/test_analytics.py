"""Tests for analytics module."""

from datetime import date, timedelta

import pytest

from grocery_tracker.analytics import Analytics
from grocery_tracker.models import (
    FrequencyData,
    LineItem,
    OutOfStockRecord,
    PriceHistory,
    PricePoint,
    PurchaseRecord,
    Receipt,
)


@pytest.fixture
def analytics(data_store):
    """Create an Analytics instance with test data store."""
    return Analytics(data_store=data_store)


class TestSpendingSummary:
    """Tests for spending summary analytics."""

    def test_empty_spending(self, analytics):
        """No receipts returns zero spending."""
        summary = analytics.spending_summary()
        assert summary.total_spending == 0.0
        assert summary.receipt_count == 0
        assert summary.item_count == 0
        assert summary.period == "monthly"

    def test_monthly_spending(self, analytics, data_store):
        """Monthly spending sums receipts in current month."""
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49),
                LineItem(item_name="Eggs", quantity=12, unit_price=0.33, total_price=3.99),
            ],
            subtotal=9.48,
            total=9.48,
        )
        data_store.save_receipt(receipt)

        summary = analytics.spending_summary(period="monthly")
        assert summary.total_spending == 9.48
        assert summary.receipt_count == 1
        assert summary.item_count == 2
        assert summary.period == "monthly"

    def test_weekly_spending(self, analytics, data_store):
        """Weekly spending uses correct date range."""
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[
                LineItem(item_name="Bread", quantity=1, unit_price=3.99, total_price=3.99),
            ],
            subtotal=3.99,
            total=3.99,
        )
        data_store.save_receipt(receipt)

        summary = analytics.spending_summary(period="weekly")
        assert summary.total_spending == 3.99
        assert summary.period == "weekly"

    def test_yearly_spending(self, analytics, data_store):
        """Yearly spending uses correct date range."""
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[
                LineItem(item_name="Rice", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=4.99,
        )
        data_store.save_receipt(receipt)

        summary = analytics.spending_summary(period="yearly")
        assert summary.total_spending == 4.99
        assert summary.period == "yearly"

    def test_spending_with_budget(self, analytics, data_store):
        """Spending with budget calculates remaining."""
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.00, total_price=5.00),
            ],
            subtotal=5.00,
            total=5.00,
        )
        data_store.save_receipt(receipt)

        summary = analytics.spending_summary(budget_limit=100.0)
        assert summary.budget_limit == 100.0
        assert summary.budget_remaining == 95.0
        assert summary.budget_percentage == 5.0

    def test_spending_category_breakdown(self, analytics, data_store):
        """Spending includes category breakdown."""
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[
                LineItem(item_name="Bananas", quantity=3, unit_price=0.49, total_price=1.47),
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49),
            ],
            subtotal=6.96,
            total=6.96,
        )
        data_store.save_receipt(receipt)

        summary = analytics.spending_summary()
        assert len(summary.categories) > 0
        assert summary.total_spending == 6.96

    def test_spending_excludes_old_receipts(self, analytics, data_store):
        """Monthly spending excludes receipts from previous months."""
        old_date = date.today().replace(day=1) - timedelta(days=1)
        receipt = Receipt(
            store_name="Giant",
            transaction_date=old_date,
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.00, total_price=5.00),
            ],
            subtotal=5.00,
            total=5.00,
        )
        data_store.save_receipt(receipt)

        summary = analytics.spending_summary(period="monthly")
        assert summary.total_spending == 0.0


class TestPriceComparison:
    """Tests for price comparison across stores."""

    def test_no_history(self, analytics):
        """Returns None when no price data exists."""
        result = analytics.price_comparison("Nonexistent")
        assert result is None

    def test_single_store(self, analytics, data_store):
        """Single store comparison returns that store as cheapest."""
        data_store.update_price("Milk", "Giant", 5.49, date.today())

        result = analytics.price_comparison("Milk")
        assert result is not None
        assert result.cheapest_store == "Giant"
        assert result.cheapest_price == 5.49
        assert result.savings == 0.0

    def test_multi_store_comparison(self, analytics, data_store):
        """Multi-store comparison finds cheapest."""
        data_store.update_price("Milk", "Giant", 5.49, date.today())
        data_store.update_price("Milk", "Trader Joe's", 4.99, date.today())

        result = analytics.price_comparison("Milk")
        assert result is not None
        assert result.cheapest_store == "Trader Joe's"
        assert result.cheapest_price == 4.99
        assert result.savings == 0.50

    def test_case_insensitive_lookup(self, analytics, data_store):
        """Price comparison matches case-insensitively."""
        data_store.update_price("Milk", "Giant", 5.49, date.today())

        result = analytics.price_comparison("milk")
        assert result is not None
        assert result.item_name == "Milk"


class TestSuggestions:
    """Tests for smart shopping suggestions."""

    def test_no_suggestions(self, analytics):
        """Returns empty list when no data exists."""
        suggestions = analytics.get_suggestions()
        assert suggestions == []

    def test_restock_suggestion(self, analytics, data_store):
        """Suggests restocking overdue items."""
        today = date.today()
        freq = FrequencyData(
            item_name="Milk",
            category="Dairy & Eggs",
            purchase_history=[
                PurchaseRecord(date=today - timedelta(days=20), quantity=1, store="Giant"),
                PurchaseRecord(date=today - timedelta(days=15), quantity=1, store="Giant"),
                PurchaseRecord(date=today - timedelta(days=10), quantity=1, store="Giant"),
            ],
        )
        data_store.save_frequency_data({"Milk": freq})

        suggestions = analytics.get_suggestions()
        restock = [s for s in suggestions if s.type == "restock"]
        assert len(restock) >= 1
        assert restock[0].item_name == "Milk"

    def test_price_alert_suggestion(self, analytics, data_store):
        """Suggests when price is significantly above average."""
        today = date.today()
        history = {
            "Eggs": {
                "Giant": PriceHistory(
                    item_name="Eggs",
                    store="Giant",
                    price_points=[
                        PricePoint(date=today - timedelta(days=30), price=3.00),
                        PricePoint(date=today - timedelta(days=20), price=3.00),
                        PricePoint(date=today - timedelta(days=10), price=5.00),
                    ],
                )
            }
        }
        data_store.save_price_history(history)

        suggestions = analytics.get_suggestions()
        price_alerts = [s for s in suggestions if s.type == "price_alert"]
        assert len(price_alerts) >= 1

    def test_out_of_stock_suggestion(self, analytics, data_store):
        """Suggests alternatives for frequently out-of-stock items."""
        record1 = OutOfStockRecord(item_name="Oat Milk", store="Giant")
        record2 = OutOfStockRecord(item_name="Oat Milk", store="Giant")
        data_store.add_out_of_stock(record1)
        data_store.add_out_of_stock(record2)

        suggestions = analytics.get_suggestions()
        oos = [s for s in suggestions if s.type == "out_of_stock"]
        assert len(oos) >= 1
        assert oos[0].item_name == "Oat Milk"

    def test_seasonal_suggestion(self, analytics, data_store):
        """Suggests seasonal items during their peak months."""
        today = date.today()
        season_month = today.month
        history = [
            PurchaseRecord(date=date(today.year - 3, season_month, 1)),
            PurchaseRecord(date=date(today.year - 3, season_month, 15)),
            PurchaseRecord(date=date(today.year - 2, season_month, 1)),
            PurchaseRecord(date=date(today.year - 2, season_month, 15)),
            PurchaseRecord(date=date(today.year - 1, season_month, 10)),
        ]
        freq = FrequencyData(item_name="Blueberries", purchase_history=history)
        data_store.save_frequency_data({"Blueberries": freq})

        suggestions = analytics.get_suggestions()
        seasonal = [s for s in suggestions if s.type == "seasonal"]
        assert len(seasonal) >= 1
        assert seasonal[0].item_name == "Blueberries"

    def test_suggestions_sorted_by_priority(self, analytics, data_store):
        """Suggestions are sorted by priority (high first)."""
        today = date.today()
        # Create overdue restock (high priority)
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[
                PurchaseRecord(date=today - timedelta(days=30), quantity=1),
                PurchaseRecord(date=today - timedelta(days=25), quantity=1),
                PurchaseRecord(date=today - timedelta(days=20), quantity=1),
            ],
        )
        data_store.save_frequency_data({"Milk": freq})

        # Create OOS record (low priority)
        for _ in range(3):
            data_store.add_out_of_stock(OutOfStockRecord(item_name="Oat Milk", store="Giant"))

        suggestions = analytics.get_suggestions()
        if len(suggestions) >= 2:
            priorities = [s.priority for s in suggestions]
            priority_order = {"high": 0, "medium": 1, "low": 2}
            ordered = [priority_order.get(p, 1) for p in priorities]
            assert ordered == sorted(ordered)


class TestOutOfStock:
    """Tests for out-of-stock recording."""

    def test_record_out_of_stock(self, analytics):
        """Can record an item as out of stock."""
        record = analytics.record_out_of_stock(
            item_name="Oat Milk",
            store="Giant",
            substitution="Almond Milk",
            reported_by="Alice",
        )
        assert record.item_name == "Oat Milk"
        assert record.store == "Giant"
        assert record.substitution == "Almond Milk"
        assert record.reported_by == "Alice"

    def test_record_without_substitution(self, analytics):
        """Can record out of stock without substitution."""
        record = analytics.record_out_of_stock(item_name="Eggs", store="Giant")
        assert record.substitution is None
        assert record.reported_by is None


class TestFrequencySummary:
    """Tests for frequency summary."""

    def test_no_data(self, analytics):
        """Returns None when no frequency data exists."""
        result = analytics.get_frequency_summary("Nonexistent")
        assert result is None

    def test_with_data(self, analytics, data_store):
        """Returns frequency data when it exists."""
        today = date.today()
        freq = FrequencyData(
            item_name="Milk",
            category="Dairy & Eggs",
            purchase_history=[
                PurchaseRecord(date=today - timedelta(days=10), quantity=1),
                PurchaseRecord(date=today - timedelta(days=5), quantity=1),
            ],
        )
        data_store.save_frequency_data({"Milk": freq})

        result = analytics.get_frequency_summary("Milk")
        assert result is not None
        assert result.item_name == "Milk"
        assert result.average_days_between_purchases == 5.0


class TestSeasonalPatterns:
    """Tests for seasonal purchase patterns."""

    def test_no_data(self, analytics):
        """Returns None when no frequency data exists."""
        result = analytics.get_seasonal_pattern("Strawberries")
        assert result is None

    def test_seasonal_pattern_detects_peak_months(self, analytics, data_store):
        """Detects peak months and season range."""
        freq = FrequencyData(
            item_name="Strawberries",
            category="Produce",
            purchase_history=[
                PurchaseRecord(date=date(2025, 5, 1)),
                PurchaseRecord(date=date(2025, 5, 15)),
                PurchaseRecord(date=date(2025, 6, 2)),
                PurchaseRecord(date=date(2025, 6, 20)),
                PurchaseRecord(date=date(2025, 7, 5)),
                PurchaseRecord(date=date(2025, 7, 22)),
                PurchaseRecord(date=date(2025, 12, 3)),
            ],
        )
        data_store.save_frequency_data({"Strawberries": freq})

        result = analytics.get_seasonal_pattern("Strawberries")
        assert result is not None
        assert result.season_range == "May-July"
        assert result.peak_months == ["May", "June", "July"]
        assert result.total_purchases == 7
        assert result.confidence == "medium"

    def test_year_round_pattern(self, analytics, data_store):
        """Flags year-round purchasing when most months have activity."""
        purchase_history = [PurchaseRecord(date=date(2025, month, 1)) for month in range(1, 13)]
        freq = FrequencyData(item_name="Milk", purchase_history=purchase_history)
        data_store.save_frequency_data({"Milk": freq})

        result = analytics.get_seasonal_pattern("Milk")
        assert result is not None
        assert result.year_round is True
        assert result.season_range == "Year-round"

    def test_seasonal_patterns_list(self, analytics, data_store):
        """Returns seasonal patterns for all items."""
        freq_apples = FrequencyData(
            item_name="Apples",
            purchase_history=[
                PurchaseRecord(date=date(2025, 9, 1)),
                PurchaseRecord(date=date(2025, 9, 15)),
                PurchaseRecord(date=date(2025, 10, 1)),
            ],
        )
        freq_strawberries = FrequencyData(
            item_name="Strawberries",
            purchase_history=[
                PurchaseRecord(date=date(2025, 5, 1)),
                PurchaseRecord(date=date(2025, 5, 15)),
            ],
        )
        data_store.save_frequency_data({"Apples": freq_apples, "Strawberries": freq_strawberries})

        patterns = analytics.get_seasonal_patterns()
        assert len(patterns) == 2
        assert patterns[0].item_name == "Apples"
        assert patterns[1].item_name == "Strawberries"


class TestCategoryGuessing:
    """Tests for category guessing heuristic."""

    def test_produce(self, analytics):
        assert analytics._guess_category("Bananas") == "Produce"
        assert analytics._guess_category("organic apples") == "Produce"

    def test_dairy(self, analytics):
        assert analytics._guess_category("Whole Milk") == "Dairy & Eggs"
        assert analytics._guess_category("Sharp Cheese") == "Dairy & Eggs"

    def test_meat(self, analytics):
        assert analytics._guess_category("Chicken Breast") == "Meat & Seafood"

    def test_bakery(self, analytics):
        assert analytics._guess_category("Sourdough Bread") == "Bakery"

    def test_beverages(self, analytics):
        assert analytics._guess_category("Kombucha") == "Beverages"

    def test_snacks(self, analytics):
        assert analytics._guess_category("Pretzels") == "Snacks"

    def test_pantry(self, analytics):
        assert analytics._guess_category("Brown Rice") == "Pantry & Canned Goods"

    def test_frozen(self, analytics):
        assert analytics._guess_category("Frozen Pizza") == "Frozen Foods"

    def test_unknown(self, analytics):
        assert analytics._guess_category("Detergent") == "Other"


class TestUpdateFrequencyFromReceipt:
    """Tests for updating frequency from receipt."""

    def test_update_from_receipt(self, analytics, data_store):
        """Updates frequency data from a receipt."""
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49),
                LineItem(item_name="Eggs", quantity=12, unit_price=0.33, total_price=3.99),
            ],
            subtotal=9.48,
            total=9.48,
        )

        analytics.update_frequency_from_receipt(receipt)

        milk_freq = data_store.get_frequency("Milk")
        assert milk_freq is not None
        assert len(milk_freq.purchase_history) == 1

        eggs_freq = data_store.get_frequency("Eggs")
        assert eggs_freq is not None
        assert len(eggs_freq.purchase_history) == 1
