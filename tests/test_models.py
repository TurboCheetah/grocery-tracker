"""Tests for data models."""

from datetime import date, datetime, timedelta
from uuid import UUID

from grocery_tracker.models import (
    BudgetTracking,
    Category,
    CategoryBudget,
    CategorySpending,
    Deal,
    DealType,
    FrequencyData,
    GroceryItem,
    GroceryList,
    InventoryItem,
    InventoryLocation,
    ItemStatus,
    LineItem,
    OutOfStockRecord,
    PriceComparison,
    PriceHistory,
    PricePoint,
    Priority,
    PurchaseRecord,
    Receipt,
    SavingsRecord,
    SavingsSummary,
    SavingsType,
    SpendingSummary,
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
            added_by="Francisco",
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
            total=12.69,
        )
        assert receipt.store_name == "Giant Food"
        assert len(receipt.line_items) == 2
        assert receipt.total == 12.69
        assert isinstance(receipt.id, UUID)


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
            reported_by="Francisco",
        )
        assert record.substitution == "Almond Milk"
        assert record.reported_by == "Francisco"


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
            logged_by="Francisco",
        )
        assert record.estimated_cost == 2.97
        assert record.logged_by == "Francisco"


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


class TestDealType:
    """Tests for DealType enum."""

    def test_values(self):
        assert DealType.COUPON.value == "coupon"
        assert DealType.SALE.value == "sale"


class TestSavingsType:
    """Tests for SavingsType enum."""

    def test_values(self):
        assert SavingsType.COUPON.value == "coupon"
        assert SavingsType.SALE.value == "sale"
        assert SavingsType.MANUAL.value == "manual"


class TestDeal:
    """Tests for Deal model."""

    def test_create_minimal(self):
        deal = Deal(item_name="Eggs", store="Giant")
        assert deal.item_name == "Eggs"
        assert deal.store == "Giant"
        assert deal.deal_type == DealType.SALE

    def test_savings_per_unit_from_prices(self):
        deal = Deal(
            item_name="Eggs",
            store="Giant",
            regular_price=3.99,
            deal_price=2.99,
        )
        assert deal.savings_per_unit == 1.00

    def test_savings_per_unit_from_percent(self):
        deal = Deal(
            item_name="Milk",
            store="Giant",
            regular_price=5.00,
            discount_percent=10,
        )
        assert deal.savings_per_unit == 0.50

    def test_active_status(self):
        today = date.today()
        active = Deal(
            item_name="Bread",
            store="Giant",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
        )
        assert active.is_active is True
        assert active.is_expired is False

        expired = Deal(
            item_name="Bread",
            store="Giant",
            end_date=today - timedelta(days=1),
        )
        assert expired.is_active is False
        assert expired.is_expired is True


class TestSavingsRecord:
    """Tests for SavingsRecord model."""

    def test_create_minimal(self):
        record = SavingsRecord(item_name="Eggs", store="Giant", savings_amount=1.50)
        assert record.item_name == "Eggs"
        assert record.store == "Giant"
        assert record.savings_type == SavingsType.MANUAL

    def test_create_full(self):
        record = SavingsRecord(
            item_name="Milk",
            store="Giant",
            savings_amount=2.00,
            regular_price=5.00,
            paid_price=3.00,
            quantity=1,
            savings_type=SavingsType.SALE,
        )
        assert record.savings_amount == 2.00
        assert record.savings_type == SavingsType.SALE


class TestSavingsSummary:
    """Tests for SavingsSummary model."""

    def test_create(self):
        summary = SavingsSummary(
            period="monthly",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            total_savings=12.0,
            savings_count=3,
            average_savings=4.0,
            by_type={"sale": 8.0, "coupon": 4.0},
            by_store={"Giant": 12.0},
            top_items=[{"item": "Eggs", "total": 5.0}],
        )
        assert summary.total_savings == 12.0
        assert summary.savings_count == 3
