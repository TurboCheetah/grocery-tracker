"""Tests for analytics module."""

from datetime import date, timedelta

import pytest

from grocery_tracker.analytics import Analytics, normalize_item_name
from grocery_tracker.list_manager import ListManager
from grocery_tracker.models import (
    FrequencyData,
    LineItem,
    OutOfStockRecord,
    PriceHistory,
    PricePoint,
    Priority,
    PurchaseRecord,
    Receipt,
    SavingsRecord,
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

    def test_spending_includes_category_inflation(self, analytics, data_store):
        """Spending summary includes category inflation with explicit windows."""
        today = date.today()
        first_half = today.replace(day=1)
        second_half = today

        if second_half == first_half:
            pytest.skip("Need at least two days in period to calculate inflation windows.")

        data_store.save_receipt(
            Receipt(
                store_name="Giant",
                transaction_date=first_half,
                line_items=[
                    LineItem(item_name="Milk", quantity=1, unit_price=4.00, total_price=4.00),
                ],
                subtotal=4.00,
                total=4.00,
            )
        )
        data_store.save_receipt(
            Receipt(
                store_name="Giant",
                transaction_date=second_half,
                line_items=[
                    LineItem(item_name="Milk", quantity=1, unit_price=5.00, total_price=5.00),
                ],
                subtotal=5.00,
                total=5.00,
            )
        )

        summary = analytics.spending_summary(period="monthly")
        assert len(summary.category_inflation) >= 1
        row = summary.category_inflation[0]
        assert row.category == "Dairy & Eggs"
        assert row.baseline_start <= row.baseline_end
        assert row.current_start <= row.current_end
        assert row.delta_pct is not None

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

    def test_time_window_metrics(self, analytics, data_store):
        """Comparison includes 30d/90d averages and deltas."""
        today = date.today()
        data_store.update_price("Milk", "Giant", 4.00, today - timedelta(days=80))
        data_store.update_price("Milk", "Giant", 5.00, today - timedelta(days=10))
        data_store.update_price("Milk", "Giant", 6.00, today)
        data_store.update_price("Milk", "TJ", 4.50, today)

        result = analytics.price_comparison("Milk")
        assert result is not None
        assert result.average_price_30d is not None
        assert result.average_price_90d is not None
        assert result.delta_vs_30d_pct is not None
        assert result.delta_vs_90d_pct is not None

    def test_canonical_grouping(self, analytics, data_store):
        """Variants of the same item are grouped by canonical identity."""
        today = date.today()
        data_store.update_price("Whole Milk 2%", "Giant", 5.49, today)
        data_store.update_price("whole   milk", "TJ", 4.99, today)

        result = analytics.price_comparison("Milk")
        assert result is not None
        assert set(result.stores.keys()) == {"Giant", "TJ"}
        assert result.cheapest_store == "TJ"

    def test_case_insensitive_lookup(self, analytics, data_store):
        """Price comparison matches case-insensitively."""
        data_store.update_price("Milk", "Giant", 5.49, date.today())

        result = analytics.price_comparison("milk")
        assert result is not None
        assert result.item_name == "Milk"


class TestSavingsSummary:
    """Tests for savings analytics summary."""

    def test_empty_savings_summary(self, analytics):
        """No savings records returns empty summary."""
        summary = analytics.savings_summary()
        assert summary.total_savings == 0.0
        assert summary.record_count == 0
        assert summary.receipt_count == 0

    def test_monthly_savings_summary(self, analytics, data_store):
        """Savings summary aggregates totals and contributors."""
        today = date.today()
        receipt = Receipt(
            store_name="Giant",
            transaction_date=today,
            line_items=[LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99)],
            subtotal=4.99,
            total=4.99,
        )
        receipt_id = data_store.save_receipt(receipt)
        data_store.add_savings_record(
            SavingsRecord(
                receipt_id=receipt_id,
                transaction_date=today,
                store="Giant",
                item_name="Milk",
                category="Dairy & Eggs",
                savings_amount=1.0,
                source="line_item_discount",
            )
        )
        data_store.add_savings_record(
            SavingsRecord(
                receipt_id=receipt_id,
                transaction_date=today,
                store="Giant",
                item_name="Eggs",
                category="Dairy & Eggs",
                savings_amount=0.5,
                source="receipt_discount",
            )
        )

        summary = analytics.savings_summary(period="monthly")
        assert summary.total_savings == 1.5
        assert summary.record_count == 2
        assert summary.receipt_count == 1
        assert summary.top_items[0].name == "Milk"
        assert summary.top_stores[0].name == "Giant"

    def test_savings_summary_excludes_old_records(self, analytics, data_store):
        """Monthly savings excludes previous-month records."""
        old_date = date.today().replace(day=1) - timedelta(days=1)
        receipt = Receipt(
            store_name="Giant",
            transaction_date=old_date,
            line_items=[LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99)],
            subtotal=4.99,
            total=4.99,
        )
        receipt_id = data_store.save_receipt(receipt)
        data_store.add_savings_record(
            SavingsRecord(
                receipt_id=receipt_id,
                transaction_date=old_date,
                store="Giant",
                item_name="Milk",
                category="Dairy & Eggs",
                savings_amount=2.0,
                source="line_item_discount",
            )
        )

        summary = analytics.savings_summary(period="monthly")
        assert summary.total_savings == 0.0


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

    def test_out_of_stock_suggestion_includes_substitutions(self, analytics, data_store):
        """Out-of-stock suggestion includes substitute candidates when available."""
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="Giant", substitution="Soy Milk")
        )
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="Giant", substitution="Almond Milk")
        )
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="TJ", substitution="Almond Milk")
        )

        suggestions = analytics.get_suggestions()
        oos = [s for s in suggestions if s.type == "out_of_stock"]
        assert len(oos) >= 1
        substitutions = oos[0].data.get("substitutions", [])
        assert len(substitutions) >= 1
        assert substitutions[0]["item_name"] == "Almond Milk"
        assert substitutions[0]["count"] == 2

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

    def test_seasonal_suggestion_with_context(self, analytics, data_store):
        """Suggests seasonal optimization with baseline and current context."""
        today = date.today()
        year = today.year - 1

        for month in (6, 7):
            for day in (3, 10, 17, 24):
                data_store.update_price(
                    "Strawberries",
                    "Giant",
                    3.00,
                    date(year, month, day),
                )

        for month in (1, 2):
            for day in (5, 19):
                data_store.update_price(
                    "Strawberries",
                    "Giant",
                    6.00,
                    date(year, month, day),
                )

        data_store.update_price("Strawberries", "Giant", 6.80, today)

        suggestions = analytics.get_suggestions()
        seasonal = [s for s in suggestions if s.type == "seasonal_optimization"]

        assert len(seasonal) == 1
        assert seasonal[0].item_name == "Strawberries"
        assert seasonal[0].priority == "high"
        assert "baseline" in seasonal[0].data
        assert "current_context" in seasonal[0].data
        assert "recommendation_reason" in seasonal[0].data
        assert seasonal[0].data["baseline"]["average_price"] == 3.0
        assert seasonal[0].data["current_context"]["latest_observed_price"] == 6.8


class TestSeasonalPurchasePattern:
    """Tests for seasonal purchase pattern analytics."""

    def test_sparse_history_returns_low_confidence(self, analytics, data_store):
        """Sparse history yields low confidence and no season windows."""
        today = date.today()
        data_store.update_price("Mango", "Giant", 2.99, today - timedelta(days=40))
        data_store.update_price("Mango", "Giant", 3.19, today - timedelta(days=5))

        pattern = analytics.seasonal_purchase_pattern("Mango")
        assert pattern is not None
        assert pattern.confidence == "low"
        assert pattern.peak_purchase_months == []
        assert pattern.low_purchase_months == []

    def test_identifies_in_season_windows(self, analytics, data_store):
        """Sufficient history identifies in-season purchase windows."""
        year = date.today().year - 1
        seasonal_counts = {1: 2, 2: 2, 3: 2, 6: 8, 7: 8, 8: 2}

        for month, count in seasonal_counts.items():
            for i in range(count):
                day = 1 + (i % 28)
                price = 2.89 if month in {6, 7} else 5.49
                data_store.update_price("Strawberries", "Giant", price, date(year, month, day))

        pattern = analytics.seasonal_purchase_pattern("Strawberries")
        assert pattern is not None
        assert pattern.sample_size == 24
        assert pattern.observed_months == 6
        assert pattern.confidence == "high"
        assert pattern.peak_purchase_months == [6, 7]
        assert 1 in pattern.low_purchase_months
        assert len(pattern.monthly_stats) == 6


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


class TestItemRecommendations:
    """Tests for item store recommendations."""

    def test_recommend_item_ranks_stores(self, analytics, data_store):
        """Recommendation ranks stores with rationale and confidence."""
        today = date.today()
        data_store.update_price("Oat Milk", "Giant", 4.99, today - timedelta(days=1))
        data_store.update_price("Oat Milk", "Giant", 5.19, today - timedelta(days=14))
        data_store.update_price("Oat Milk", "TJ", 4.49, today - timedelta(days=2))
        data_store.update_price("Oat Milk", "TJ", 4.59, today - timedelta(days=12))
        data_store.update_price("Oat Milk", "Whole Foods", 5.89, today - timedelta(days=3))
        data_store.update_price("Oat Milk", "Whole Foods", 5.99, today - timedelta(days=20))
        data_store.add_out_of_stock(OutOfStockRecord(item_name="Oat Milk", store="Giant"))
        data_store.add_out_of_stock(OutOfStockRecord(item_name="Oat Milk", store="Giant"))

        recommendation = analytics.recommend_item("Oat Milk")
        assert recommendation is not None
        assert recommendation.recommended_store == "TJ"
        assert recommendation.confidence in {"medium", "high"}
        assert len(recommendation.ranked_stores) == 3
        assert recommendation.ranked_stores[0].store == "TJ"
        assert recommendation.ranked_stores[0].rank == 1
        assert len(recommendation.ranked_stores[0].rationale) >= 1

    def test_recommend_item_returns_none_for_low_confidence(self, analytics, data_store):
        """No recommendation is returned when confidence is below threshold."""
        data_store.update_price("Milk", "Giant", 5.49, date.today() - timedelta(days=300))

        recommendation = analytics.recommend_item("Milk")
        assert recommendation is None

    def test_recommend_item_substitutions_are_deterministic(self, analytics, data_store):
        """Substitution ranking is deterministic for equal-count outcomes."""
        today = date.today()
        data_store.update_price("Oat Milk", "Giant", 4.99, today - timedelta(days=1))
        data_store.update_price("Oat Milk", "TJ", 4.69, today - timedelta(days=2))
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="Giant", substitution="Soy Milk")
        )
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="Giant", substitution="Almond Milk")
        )
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="TJ", substitution="Almond Milk")
        )
        data_store.add_out_of_stock(
            OutOfStockRecord(item_name="Oat Milk", store="TJ", substitution="Soy Milk")
        )

        recommendation = analytics.recommend_item("Oat Milk")
        assert recommendation is not None
        assert len(recommendation.substitutions) >= 2
        assert recommendation.substitutions[0].item_name == "Almond Milk"
        assert recommendation.substitutions[1].item_name == "Soy Milk"


class TestShoppingRoutePlanner:
    """Tests for deterministic shopping route planning."""

    def test_route_empty_when_no_pending_items(self, analytics):
        """Empty list returns a route with no stops."""
        route = analytics.plan_shopping_route()
        assert route.total_items == 0
        assert route.stops == []
        assert route.unassigned_items == []

    def test_route_assigns_items_and_uses_recommendations(self, analytics, data_store):
        """Items are assigned by store preference or recommendation."""
        manager = ListManager(data_store=data_store)
        manager.add_item(name="Apples", store="Giant", priority=Priority.HIGH)
        manager.add_item(name="Milk", priority=Priority.MEDIUM)

        today = date.today()
        data_store.update_price("Milk", "TJ", 4.79, today - timedelta(days=1))
        data_store.update_price("Milk", "TJ", 4.89, today - timedelta(days=8))
        data_store.update_price("Milk", "Giant", 5.29, today - timedelta(days=2))
        data_store.update_price("Milk", "Giant", 5.19, today - timedelta(days=7))

        route = analytics.plan_shopping_route()
        assert route.total_items == 2
        assert len(route.stops) == 2

        assignments = {
            assignment.item_name: assignment
            for stop in route.stops
            for assignment in stop.items
        }
        assert assignments["Apples"].assigned_store == "Giant"
        assert assignments["Apples"].assignment_source == "list_preference"
        assert assignments["Milk"].assigned_store == "TJ"
        assert assignments["Milk"].assignment_source in {"recommendation", "price_history"}

    def test_route_store_order_is_deterministic(self, analytics, data_store):
        """Store order is stable for tied stop metrics."""
        manager = ListManager(data_store=data_store)
        manager.add_item(name="Sourdough", store="Whole Foods", priority=Priority.HIGH)
        manager.add_item(name="Bananas", store="Giant", priority=Priority.HIGH)
        manager.add_item(name="Pasta", store="Aldi", priority=Priority.LOW)

        route = analytics.plan_shopping_route()
        stores = [stop.store for stop in route.stops]
        assert stores == ["Giant", "Whole Foods", "Aldi"]

    def test_route_unassigned_items_when_no_store_or_history(self, analytics, data_store):
        """Items with no store and no history are left unassigned."""
        manager = ListManager(data_store=data_store)
        manager.add_item(name="Paprika")

        route = analytics.plan_shopping_route()
        assert route.total_items == 1
        assert route.stops == []
        assert len(route.unassigned_items) == 1
        assert route.unassigned_items[0].item_name == "Paprika"
        assert route.unassigned_items[0].assignment_source == "unassigned"


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

    def test_canonical_frequency_merge(self, analytics, data_store):
        """Frequency lookup merges canonical item variants."""
        today = date.today()
        data_store.save_frequency_data(
            {
                "Whole Milk 2%": FrequencyData(
                    item_name="Whole Milk 2%",
                    purchase_history=[PurchaseRecord(date=today - timedelta(days=8), quantity=1)],
                ),
                "whole milk": FrequencyData(
                    item_name="whole milk",
                    purchase_history=[PurchaseRecord(date=today - timedelta(days=2), quantity=1)],
                ),
            }
        )

        result = analytics.get_frequency_summary("Milk")
        assert result is not None
        assert len(result.purchase_history) == 2


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


class TestItemNormalization:
    """Tests for canonical item name normalization."""

    def test_normalize_spacing_and_case(self):
        assert normalize_item_name("  Whole   MILK ") == "milk"

    def test_normalize_suffix_tokens(self):
        assert normalize_item_name("Organic Bananas 16oz") == "bananas"


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
