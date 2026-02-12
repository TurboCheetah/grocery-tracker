"""Tests for data models."""

from datetime import date, datetime, timedelta
from uuid import UUID

from grocery_tracker.models import (
    BudgetTracking,
    BulkBuyingAnalysis,
    BulkPackOption,
    Category,
    CategoryBudget,
    CategoryInflation,
    CategorySpending,
    FrequencyData,
    GroceryItem,
    GroceryList,
    InventoryItem,
    InventoryLocation,
    ItemRecommendation,
    ItemStatus,
    LineItem,
    OutOfStockRecord,
    PriceComparison,
    PriceHistory,
    PricePoint,
    Priority,
    PurchaseRecord,
    Receipt,
    RecipeHookItem,
    RecipeHookPayload,
    RouteItemAssignment,
    RouteStoreStop,
    SavingsContributor,
    SavingsRecord,
    SavingsSummary,
    SeasonalMonthStat,
    SeasonalPurchasePattern,
    ShoppingRoute,
    SpendingSummary,
    StorePreferenceScore,
    SubstitutionRecommendation,
    Suggestion,
    WasteReason,
    WasteRecord,
)


class TestGroceryItem:
    """Tests for GroceryItem model."""

    def test_create_minimal(self):
        """Create item with only required fields."""
        item = GroceryItem(name="Milk")
        assert item.name == "Milk"
        assert item.quantity == 1
        assert item.status == ItemStatus.TO_BUY
        assert item.priority == Priority.MEDIUM
        assert isinstance(item.id, UUID)
        assert isinstance(item.added_at, datetime)

    def test_create_full(self):
        """Create item with all fields."""
        item = GroceryItem(
            name="Organic Milk",
            quantity=2,
            unit="gallon",
            category=Category.DAIRY.value,
            store="Giant",
            aisle="7A",
            brand_preference="Horizon",
            estimated_price=5.99,
            priority=Priority.HIGH,
            added_by="Alice",
            notes="Whole milk only",
        )
        assert item.name == "Organic Milk"
        assert item.quantity == 2
        assert item.unit == "gallon"
        assert item.store == "Giant"
        assert item.brand_preference == "Horizon"
        assert item.priority == Priority.HIGH

    def test_quantity_can_be_string(self):
        """Quantity can be a string like '1-2' or 'a few'."""
        item = GroceryItem(name="Apples", quantity="5-6")
        assert item.quantity == "5-6"


class TestLineItem:
    """Tests for LineItem model."""

    def test_create_line_item(self):
        """Create a receipt line item."""
        item = LineItem(
            item_name="Bananas",
            quantity=3,
            unit_price=0.59,
            total_price=1.77,
        )
        assert item.item_name == "Bananas"
        assert item.quantity == 3
        assert item.unit_price == 0.59
        assert item.total_price == 1.77
        assert item.matched_list_item_id is None
        assert item.sale is False
        assert item.discount_amount == 0.0
        assert item.coupon_amount == 0.0
        assert item.regular_unit_price is None


class TestReceipt:
    """Tests for Receipt model."""

    def test_create_receipt(self):
        """Create a receipt with line items."""
        receipt = Receipt(
            store_name="Giant Food",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
                LineItem(item_name="Bread", quantity=2, unit_price=3.49, total_price=6.98),
            ],
            subtotal=11.97,
            tax=0.72,
            discount_total=1.25,
            coupon_total=0.5,
            total=12.69,
        )
        assert receipt.store_name == "Giant Food"
        assert len(receipt.line_items) == 2
        assert receipt.total == 12.69
        assert receipt.discount_total == 1.25
        assert receipt.coupon_total == 0.5
        assert isinstance(receipt.id, UUID)


class TestSavingsModels:
    """Tests for savings models."""

    def test_create_savings_record(self):
        """Create a savings record."""
        record = SavingsRecord(
            receipt_id=UUID("11111111-1111-1111-1111-111111111111"),
            transaction_date=date.today(),
            store="Giant",
            item_name="Milk",
            category="Dairy & Eggs",
            savings_amount=1.25,
            source="line_item_discount",
            quantity=1.0,
            paid_unit_price=4.99,
            regular_unit_price=6.24,
        )
        assert record.savings_amount == 1.25
        assert record.store == "Giant"

    def test_create_savings_summary(self):
        """Create a savings summary."""
        summary = SavingsSummary(
            period="monthly",
            start_date=date.today(),
            end_date=date.today(),
            total_savings=5.0,
            receipt_count=2,
            record_count=3,
            top_items=[SavingsContributor(name="Milk", total_savings=3.0, record_count=2)],
        )
        assert summary.total_savings == 5.0
        assert summary.top_items[0].name == "Milk"


class TestSeasonalModels:
    """Tests for seasonal analytics models."""

    def test_create_seasonal_month_stat(self):
        """Seasonal month stat captures count and price."""
        stat = SeasonalMonthStat(month=6, purchase_count=5, average_price=3.49)
        assert stat.month == 6
        assert stat.purchase_count == 5
        assert stat.average_price == 3.49

    def test_create_seasonal_purchase_pattern(self):
        """Seasonal purchase pattern captures windows and confidence."""
        pattern = SeasonalPurchasePattern(
            item_name="Strawberries",
            sample_size=24,
            observed_months=6,
            peak_purchase_months=[6, 7],
            low_purchase_months=[1, 2],
            monthly_stats=[
                SeasonalMonthStat(month=6, purchase_count=8, average_price=2.99),
                SeasonalMonthStat(month=1, purchase_count=2, average_price=5.99),
            ],
            confidence="high",
        )
        assert pattern.item_name == "Strawberries"
        assert pattern.sample_size == 24
        assert pattern.peak_purchase_months == [6, 7]
        assert pattern.confidence == "high"


class TestBulkModels:
    """Tests for bulk buying models."""

    def test_create_bulk_pack_option(self):
        option = BulkPackOption(
            name="bulk",
            quantity=12,
            unit="count",
            pack_price=14.4,
            normalized_quantity=12,
            normalized_unit="count",
            unit_price=1.2,
        )
        assert option.name == "bulk"
        assert option.unit_price == 1.2

    def test_create_bulk_buying_analysis(self):
        analysis = BulkBuyingAnalysis(
            item_name="Soda",
            comparable=True,
            comparison_status="ok",
            standard_option=BulkPackOption(
                name="standard",
                quantity=1,
                unit="count",
                pack_price=1.5,
                unit_price=1.5,
            ),
            bulk_option=BulkPackOption(
                name="bulk",
                quantity=12,
                unit="count",
                pack_price=14.4,
                unit_price=1.2,
            ),
            recommended_option="bulk",
            break_even_recommendation="Bulk breaks even after 3 packs.",
        )
        assert analysis.comparable is True
        assert analysis.recommended_option == "bulk"

    def test_create_bulk_buying_analysis_non_comparable_defaults(self):
        """Non-comparable analysis keeps optional defaults."""
        analysis = BulkBuyingAnalysis(
            item_name="Milk",
            comparable=False,
            comparison_status="unit_mismatch",
            standard_option=BulkPackOption(
                name="standard",
                quantity=64,
                unit="oz",
                pack_price=4.99,
            ),
            bulk_option=BulkPackOption(
                name="bulk",
                quantity=1,
                unit="count",
                pack_price=4.99,
            ),
            break_even_recommendation=(
                "Unable to compare pack options because units are not compatible."
            ),
        )
        assert analysis.break_even_units is None
        assert analysis.projected_monthly_savings is None
        assert analysis.assumptions == []


class TestRecipeHookModels:
    """Tests for recipe hook payload models."""

    def test_create_recipe_hook_item_defaults(self):
        """Recipe hook item applies expected defaults."""
        item = RecipeHookItem(item_name="Milk", quantity=1)
        assert item.category == Category.OTHER.value
        assert item.location == InventoryLocation.PANTRY
        assert item.priority_rank == 0

    def test_create_recipe_hook_payload(self):
        payload = RecipeHookPayload(
            horizon_days=3,
            expiring_items=[
                RecipeHookItem(
                    item_name="Milk",
                    quantity=1,
                    unit="carton",
                    expiration_date=date.today() + timedelta(days=1),
                    days_until_expiration=1,
                    priority_rank=1,
                )
            ],
            priority_order=["Milk"],
            constraints={"dietary_restrictions": ["vegetarian"], "allergens": ["peanuts"]},
        )
        assert payload.horizon_days == 3
        assert payload.expiring_items[0].item_name == "Milk"
        assert payload.priority_order == ["Milk"]


class TestPriceHistory:
    """Tests for PriceHistory model."""

    def test_empty_history(self):
        """Empty price history returns None for all computed properties."""
        history = PriceHistory(item_name="Milk", store="Giant")
        assert history.current_price is None
        assert history.average_price is None
        assert history.lowest_price is None
        assert history.highest_price is None

    def test_price_calculations(self):
        """Price history calculates statistics correctly."""
        history = PriceHistory(
            item_name="Milk",
            store="Giant",
            price_points=[
                PricePoint(date=date(2024, 1, 1), price=4.99),
                PricePoint(date=date(2024, 1, 8), price=5.49),
                PricePoint(date=date(2024, 1, 15), price=4.49, sale=True),
            ],
        )
        assert history.current_price == 4.49  # Most recent
        assert history.lowest_price == 4.49
        assert history.highest_price == 5.49
        assert abs(history.average_price - 4.99) < 0.01


class TestGroceryList:
    """Tests for GroceryList model."""

    def test_create_empty_list(self):
        """Create empty grocery list."""
        grocery_list = GroceryList()
        assert grocery_list.version == "1.0"
        assert grocery_list.items == []
        assert isinstance(grocery_list.last_updated, datetime)

    def test_create_list_with_items(self):
        """Create grocery list with items."""
        items = [
            GroceryItem(name="Milk"),
            GroceryItem(name="Bread"),
        ]
        grocery_list = GroceryList(items=items)
        assert len(grocery_list.items) == 2


class TestEnums:
    """Tests for enum values."""

    def test_priority_values(self):
        """Priority enum has expected values."""
        assert Priority.HIGH.value == "high"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.LOW.value == "low"

    def test_item_status_values(self):
        """ItemStatus enum has expected values."""
        assert ItemStatus.TO_BUY.value == "to_buy"
        assert ItemStatus.BOUGHT.value == "bought"
        assert ItemStatus.STILL_NEEDED.value == "still_needed"

    def test_category_values(self):
        """Category enum has expected values."""
        assert Category.PRODUCE.value == "Produce"
        assert Category.DAIRY.value == "Dairy & Eggs"
        assert Category.FROZEN.value == "Frozen Foods"


class TestFrequencyData:
    """Tests for FrequencyData model."""

    def test_empty_history(self):
        """Empty history returns None for computed props."""
        freq = FrequencyData(item_name="Milk")
        assert freq.average_days_between_purchases is None
        assert freq.last_purchased is None
        assert freq.next_expected_purchase is None
        assert freq.days_since_last_purchase is None
        assert freq.confidence == "low"

    def test_single_purchase(self):
        """Single purchase can't compute average interval."""
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[PurchaseRecord(date=date.today())],
        )
        assert freq.average_days_between_purchases is None
        assert freq.last_purchased == date.today()
        assert freq.days_since_last_purchase == 0
        assert freq.confidence == "low"

    def test_multiple_purchases(self):
        """Multiple purchases compute average interval."""
        today = date.today()
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[
                PurchaseRecord(date=today - timedelta(days=10)),
                PurchaseRecord(date=today - timedelta(days=5)),
                PurchaseRecord(date=today),
            ],
        )
        assert freq.average_days_between_purchases == 5.0
        assert freq.last_purchased == today
        assert freq.days_since_last_purchase == 0

    def test_next_expected_purchase(self):
        """Next expected purchase is computed from average interval."""
        today = date.today()
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[
                PurchaseRecord(date=today - timedelta(days=10)),
                PurchaseRecord(date=today - timedelta(days=5)),
            ],
        )
        expected = (today - timedelta(days=5)) + timedelta(days=5)
        assert freq.next_expected_purchase == expected

    def test_confidence_low(self):
        """Confidence is low with < 5 purchases."""
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[PurchaseRecord(date=date.today()) for _ in range(3)],
        )
        assert freq.confidence == "low"

    def test_confidence_medium(self):
        """Confidence is medium with 5-9 purchases."""
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[PurchaseRecord(date=date.today()) for _ in range(7)],
        )
        assert freq.confidence == "medium"

    def test_confidence_high(self):
        """Confidence is high with 10+ purchases."""
        freq = FrequencyData(
            item_name="Milk",
            purchase_history=[PurchaseRecord(date=date.today()) for _ in range(12)],
        )
        assert freq.confidence == "high"


class TestPurchaseRecord:
    """Tests for PurchaseRecord model."""

    def test_create_minimal(self):
        """Create record with defaults."""
        record = PurchaseRecord(date=date.today())
        assert record.quantity == 1.0
        assert record.store is None

    def test_create_full(self):
        """Create record with all fields."""
        record = PurchaseRecord(date=date.today(), quantity=3, store="Giant")
        assert record.quantity == 3
        assert record.store == "Giant"


class TestOutOfStockRecord:
    """Tests for OutOfStockRecord model."""

    def test_create_minimal(self):
        """Create record with required fields."""
        record = OutOfStockRecord(item_name="Oat Milk", store="Giant")
        assert record.item_name == "Oat Milk"
        assert record.store == "Giant"
        assert record.recorded_date == date.today()
        assert record.substitution is None
        assert record.reported_by is None
        assert isinstance(record.id, UUID)

    def test_create_full(self):
        """Create record with all fields."""
        record = OutOfStockRecord(
            item_name="Oat Milk",
            store="Giant",
            substitution="Almond Milk",
            reported_by="Alice",
        )
        assert record.substitution == "Almond Milk"
        assert record.reported_by == "Alice"


class TestCategorySpending:
    """Tests for CategorySpending model."""

    def test_create(self):
        """Create category spending."""
        cs = CategorySpending(category="Produce", total=80.00, percentage=18.0, item_count=15)
        assert cs.category == "Produce"
        assert cs.total == 80.00
        assert cs.percentage == 18.0
        assert cs.item_count == 15


class TestSpendingSummary:
    """Tests for SpendingSummary model."""

    def test_create_minimal(self):
        """Create summary without budget."""
        summary = SpendingSummary(
            period="monthly",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            total_spending=450.00,
            receipt_count=8,
            item_count=45,
        )
        assert summary.period == "monthly"
        assert summary.total_spending == 450.00
        assert summary.budget_limit is None
        assert summary.category_inflation == []

    def test_create_with_budget(self):
        """Create summary with budget."""
        summary = SpendingSummary(
            period="monthly",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            total_spending=450.00,
            receipt_count=8,
            item_count=45,
            budget_limit=500.00,
            budget_remaining=50.00,
            budget_percentage=90.0,
        )
        assert summary.budget_limit == 500.00
        assert summary.budget_remaining == 50.00
        assert summary.budget_percentage == 90.0


class TestCategoryInflation:
    """Tests for CategoryInflation model."""

    def test_create(self):
        row = CategoryInflation(
            category="Dairy & Eggs",
            baseline_start=date(2026, 1, 1),
            baseline_end=date(2026, 1, 15),
            current_start=date(2026, 1, 16),
            current_end=date(2026, 1, 31),
            baseline_avg_price=4.0,
            current_avg_price=5.0,
            delta_pct=25.0,
            baseline_samples=3,
            current_samples=4,
        )
        assert row.category == "Dairy & Eggs"
        assert row.delta_pct == 25.0


class TestPriceComparison:
    """Tests for PriceComparison model."""

    def test_create(self):
        """Create price comparison."""
        comp = PriceComparison(
            item_name="Milk",
            stores={"Giant": 5.49, "TJ": 4.99},
            cheapest_store="TJ",
            cheapest_price=4.99,
            savings=0.50,
        )
        assert comp.cheapest_store == "TJ"
        assert comp.savings == 0.50

    def test_create_with_window_metrics(self):
        """Create price comparison with windowed metric fields."""
        comp = PriceComparison(
            item_name="Milk",
            stores={"Giant": 5.49},
            average_price_30d=5.10,
            average_price_90d=4.90,
            delta_vs_30d_pct=7.6,
            delta_vs_90d_pct=12.0,
        )
        assert comp.average_price_30d == 5.10
        assert comp.delta_vs_90d_pct == 12.0


class TestSuggestion:
    """Tests for Suggestion model."""

    def test_create_restock(self):
        """Create restock suggestion."""
        s = Suggestion(
            type="restock",
            item_name="Milk",
            message="Usually buy every 5 days, last purchase 7 days ago",
            priority="high",
        )
        assert s.type == "restock"
        assert s.priority == "high"

    def test_create_with_data(self):
        """Create suggestion with extra data."""
        s = Suggestion(
            type="price_alert",
            item_name="Eggs",
            message="Price up 20%",
            data={"current": 4.99, "average": 3.99},
        )
        assert s.data["current"] == 4.99


class TestStorePreferenceScore:
    """Tests for StorePreferenceScore model."""

    def test_create(self):
        score = StorePreferenceScore(
            store="TJ",
            rank=1,
            score=0.82,
            current_price=4.99,
            average_price=5.10,
            out_of_stock_count=0,
            samples=4,
            recency_days=3,
        )
        assert score.store == "TJ"
        assert score.rank == 1
        assert score.score == 0.82


class TestSubstitutionRecommendation:
    """Tests for SubstitutionRecommendation model."""

    def test_create(self):
        sub = SubstitutionRecommendation(
            item_name="Almond Milk",
            count=3,
            stores=["Giant", "TJ"],
        )
        assert sub.item_name == "Almond Milk"
        assert sub.count == 3
        assert sub.stores == ["Giant", "TJ"]


class TestItemRecommendation:
    """Tests for ItemRecommendation model."""

    def test_create(self):
        rec = ItemRecommendation(
            item_name="Milk",
            confidence="high",
            confidence_score=0.85,
            recommended_store="TJ",
            ranked_stores=[
                StorePreferenceScore(
                    store="TJ",
                    rank=1,
                    score=0.85,
                    current_price=4.99,
                    average_price=5.05,
                )
            ],
            substitutions=[SubstitutionRecommendation(item_name="Almond Milk", count=2)],
        )
        assert rec.item_name == "Milk"
        assert rec.recommended_store == "TJ"
        assert rec.ranked_stores[0].store == "TJ"
        assert rec.substitutions[0].item_name == "Almond Milk"


class TestRouteItemAssignment:
    """Tests for RouteItemAssignment model."""

    def test_create(self):
        assignment = RouteItemAssignment(
            item_name="Milk",
            quantity=1,
            category="Dairy & Eggs",
            priority=Priority.HIGH,
            assigned_store="TJ",
            estimated_price=4.99,
            assignment_source="recommendation",
        )
        assert assignment.item_name == "Milk"
        assert assignment.assigned_store == "TJ"
        assert assignment.priority == Priority.HIGH


class TestRouteStoreStop:
    """Tests for RouteStoreStop model."""

    def test_create(self):
        stop = RouteStoreStop(
            stop_number=1,
            store="TJ",
            items=[RouteItemAssignment(item_name="Milk", assigned_store="TJ")],
            item_count=1,
            estimated_total=4.99,
        )
        assert stop.stop_number == 1
        assert stop.store == "TJ"
        assert stop.item_count == 1


class TestShoppingRoute:
    """Tests for ShoppingRoute model."""

    def test_create(self):
        route = ShoppingRoute(
            total_items=2,
            total_estimated_cost=9.98,
            stops=[
                RouteStoreStop(
                    stop_number=1,
                    store="TJ",
                    item_count=2,
                    estimated_total=9.98,
                )
            ],
        )
        assert route.total_items == 2
        assert route.stops[0].store == "TJ"
        assert route.total_estimated_cost == 9.98


# --- Phase 3 Model Tests ---


class TestInventoryLocation:
    """Tests for InventoryLocation enum."""

    def test_values(self):
        assert InventoryLocation.PANTRY.value == "pantry"
        assert InventoryLocation.FRIDGE.value == "fridge"
        assert InventoryLocation.FREEZER.value == "freezer"


class TestWasteReason:
    """Tests for WasteReason enum."""

    def test_values(self):
        assert WasteReason.SPOILED.value == "spoiled"
        assert WasteReason.NEVER_USED.value == "never_used"
        assert WasteReason.OVERRIPE.value == "overripe"
        assert WasteReason.OTHER.value == "other"


class TestInventoryItem:
    """Tests for InventoryItem model."""

    def test_create_basic(self):
        item = InventoryItem(item_name="Milk")
        assert item.item_name == "Milk"
        assert item.quantity == 1.0
        assert item.location == InventoryLocation.PANTRY
        assert isinstance(item.id, UUID)

    def test_create_full(self):
        exp = date.today() + timedelta(days=7)
        item = InventoryItem(
            item_name="Yogurt",
            category="Dairy & Eggs",
            quantity=3.0,
            unit="cups",
            location=InventoryLocation.FRIDGE,
            expiration_date=exp,
            low_stock_threshold=2.0,
        )
        assert item.expiration_date == exp
        assert item.location == InventoryLocation.FRIDGE

    def test_is_expired_false(self):
        item = InventoryItem(
            item_name="Milk",
            expiration_date=date.today() + timedelta(days=5),
        )
        assert item.is_expired is False

    def test_is_expired_true(self):
        item = InventoryItem(
            item_name="Milk",
            expiration_date=date.today() - timedelta(days=1),
        )
        assert item.is_expired is True

    def test_is_expired_none(self):
        item = InventoryItem(item_name="Rice")
        assert item.is_expired is False

    def test_is_low_stock(self):
        item = InventoryItem(item_name="Eggs", quantity=1.0, low_stock_threshold=3.0)
        assert item.is_low_stock is True

    def test_not_low_stock(self):
        item = InventoryItem(item_name="Eggs", quantity=10.0, low_stock_threshold=3.0)
        assert item.is_low_stock is False

    def test_days_until_expiration(self):
        item = InventoryItem(
            item_name="Milk",
            expiration_date=date.today() + timedelta(days=5),
        )
        assert item.days_until_expiration == 5

    def test_days_until_expiration_none(self):
        item = InventoryItem(item_name="Rice")
        assert item.days_until_expiration is None


class TestWasteRecord:
    """Tests for WasteRecord model."""

    def test_create_basic(self):
        record = WasteRecord(item_name="Bread", reason=WasteReason.SPOILED)
        assert record.item_name == "Bread"
        assert record.reason == WasteReason.SPOILED
        assert record.waste_logged_date == date.today()

    def test_create_full(self):
        record = WasteRecord(
            item_name="Bell Peppers",
            quantity=3.0,
            unit="pieces",
            reason=WasteReason.OVERRIPE,
            estimated_cost=2.97,
            original_purchase_date=date.today() - timedelta(days=5),
            logged_by="Alice",
        )
        assert record.estimated_cost == 2.97
        assert record.logged_by == "Alice"


class TestCategoryBudget:
    """Tests for CategoryBudget model."""

    def test_remaining(self):
        cb = CategoryBudget(category="Produce", limit=100.0, spent=80.0)
        assert cb.remaining == 20.0

    def test_percentage_used(self):
        cb = CategoryBudget(category="Produce", limit=100.0, spent=75.0)
        assert cb.percentage_used == 75.0

    def test_is_over_budget(self):
        cb = CategoryBudget(category="Produce", limit=100.0, spent=110.0)
        assert cb.is_over_budget is True

    def test_not_over_budget(self):
        cb = CategoryBudget(category="Produce", limit=100.0, spent=80.0)
        assert cb.is_over_budget is False

    def test_zero_limit(self):
        cb = CategoryBudget(category="Produce", limit=0.0, spent=0.0)
        assert cb.percentage_used == 0.0


class TestBudgetTracking:
    """Tests for BudgetTracking model."""

    def test_create(self):
        bt = BudgetTracking(month="2026-01", monthly_limit=500.0)
        assert bt.month == "2026-01"
        assert bt.monthly_limit == 500.0
        assert bt.total_spent == 0.0

    def test_total_remaining(self):
        bt = BudgetTracking(month="2026-01", monthly_limit=500.0, total_spent=350.0)
        assert bt.total_remaining == 150.0

    def test_total_percentage(self):
        bt = BudgetTracking(month="2026-01", monthly_limit=500.0, total_spent=250.0)
        assert bt.total_percentage_used == 50.0

    def test_zero_limit(self):
        bt = BudgetTracking(month="2026-01", monthly_limit=0.0)
        assert bt.total_percentage_used == 0.0

    def test_with_categories(self):
        bt = BudgetTracking(
            month="2026-01",
            monthly_limit=500.0,
            category_budgets=[
                CategoryBudget(category="Produce", limit=100.0),
                CategoryBudget(category="Dairy & Eggs", limit=80.0),
            ],
        )
        assert len(bt.category_budgets) == 2
