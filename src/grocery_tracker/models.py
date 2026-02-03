"""Core data models for Grocery Tracker."""

from datetime import date, datetime, time
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Item priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ItemStatus(str, Enum):
    """Item status in shopping list."""

    TO_BUY = "to_buy"
    BOUGHT = "bought"
    STILL_NEEDED = "still_needed"


class Category(str, Enum):
    """Product categories."""

    PRODUCE = "Produce"
    DAIRY = "Dairy & Eggs"
    MEAT = "Meat & Seafood"
    BAKERY = "Bakery"
    PANTRY = "Pantry & Canned Goods"
    FROZEN = "Frozen Foods"
    BEVERAGES = "Beverages"
    SNACKS = "Snacks"
    HEALTH = "Health & Beauty"
    HOUSEHOLD = "Household Supplies"
    OTHER = "Other"


class GroceryItem(BaseModel):
    """A grocery list item."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    quantity: int | float | str = 1
    unit: str | None = None
    category: str = Category.OTHER.value
    store: str | None = None
    aisle: str | None = None
    brand_preference: str | None = None
    estimated_price: float | None = None
    priority: Priority = Priority.MEDIUM
    added_by: str | None = None
    added_at: datetime = Field(default_factory=datetime.now)
    notes: str | None = None
    status: ItemStatus = ItemStatus.TO_BUY


class LineItem(BaseModel):
    """A line item from a receipt."""

    item_name: str
    quantity: float = 1.0
    unit_price: float
    total_price: float
    matched_list_item_id: UUID | None = None


class Receipt(BaseModel):
    """A processed receipt."""

    id: UUID = Field(default_factory=uuid4)
    store_name: str
    store_location: str | None = None
    transaction_date: date
    transaction_time: time | None = None
    purchased_by: str | None = None
    line_items: list[LineItem]
    subtotal: float
    tax: float = 0.0
    total: float
    payment_method: str | None = None
    receipt_image_path: str | None = None
    raw_ocr_text: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class PricePoint(BaseModel):
    """A single price observation."""

    date: date
    price: float
    unit: str | None = None
    sale: bool = False
    receipt_id: UUID | None = None


class PriceHistory(BaseModel):
    """Price history for an item at a store."""

    item_name: str
    store: str
    price_points: list[PricePoint] = Field(default_factory=list)

    @property
    def current_price(self) -> float | None:
        """Get most recent price."""
        if not self.price_points:
            return None
        return sorted(self.price_points, key=lambda p: p.date, reverse=True)[0].price

    @property
    def average_price(self) -> float | None:
        """Get average price."""
        if not self.price_points:
            return None
        return sum(p.price for p in self.price_points) / len(self.price_points)

    @property
    def lowest_price(self) -> float | None:
        """Get lowest historical price."""
        if not self.price_points:
            return None
        return min(p.price for p in self.price_points)

    @property
    def highest_price(self) -> float | None:
        """Get highest historical price."""
        if not self.price_points:
            return None
        return max(p.price for p in self.price_points)


class GroceryList(BaseModel):
    """The complete grocery list."""

    version: str = "1.0"
    last_updated: datetime = Field(default_factory=datetime.now)
    items: list[GroceryItem] = Field(default_factory=list)


class UserPreferences(BaseModel):
    """User preferences and settings."""

    user: str
    brand_preferences: dict[str, str] = Field(default_factory=dict)
    dietary_restrictions: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    favorite_items: list[str] = Field(default_factory=list)
    shopping_patterns: dict[str, Any] = Field(default_factory=dict)


class ReconciliationResult(BaseModel):
    """Result of reconciling a receipt with the shopping list."""

    receipt_id: UUID
    matched_items: int
    still_needed: list[str]
    newly_bought: list[str]
    total_spent: float
    items_purchased: int


class PurchaseRecord(BaseModel):
    """A single purchase occurrence for frequency tracking."""

    date: date
    quantity: float = 1.0
    store: str | None = None


class FrequencyData(BaseModel):
    """Purchase frequency tracking for an item."""

    item_name: str
    category: str = "Other"
    purchase_history: list[PurchaseRecord] = Field(default_factory=list)

    @property
    def average_days_between_purchases(self) -> float | None:
        """Calculate average days between purchases."""
        if len(self.purchase_history) < 2:
            return None
        dates = sorted(p.date for p in self.purchase_history)
        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        return sum(intervals) / len(intervals)

    @property
    def last_purchased(self) -> date | None:
        """Get last purchase date."""
        if not self.purchase_history:
            return None
        return max(p.date for p in self.purchase_history)

    @property
    def next_expected_purchase(self) -> date | None:
        """Calculate next expected purchase date."""
        avg = self.average_days_between_purchases
        last = self.last_purchased
        if avg is None or last is None:
            return None
        from datetime import timedelta

        return last + timedelta(days=round(avg))

    @property
    def days_since_last_purchase(self) -> int | None:
        """Days since last purchase."""
        last = self.last_purchased
        if last is None:
            return None
        return (date.today() - last).days

    @property
    def confidence(self) -> str:
        """Confidence level based on purchase history size."""
        count = len(self.purchase_history)
        if count >= 10:
            return "high"
        elif count >= 5:
            return "medium"
        return "low"


class SeasonalMonth(BaseModel):
    """Monthly purchase counts for seasonal analysis."""

    month: int
    month_name: str
    purchase_count: int
    percentage: float


class SeasonalPattern(BaseModel):
    """Seasonal purchasing pattern for an item."""

    item_name: str
    total_purchases: int
    months: list[SeasonalMonth] = Field(default_factory=list)
    peak_months: list[str] = Field(default_factory=list)
    season_range: str | None = None
    year_round: bool = False
    confidence: str = "low"


class OutOfStockRecord(BaseModel):
    """Record of an item being out of stock at a store."""

    id: UUID = Field(default_factory=uuid4)
    item_name: str
    store: str
    recorded_date: date = Field(default_factory=date.today)
    substitution: str | None = None
    reported_by: str | None = None


class CategorySpending(BaseModel):
    """Spending breakdown for a category."""

    category: str
    total: float
    percentage: float
    item_count: int


class SpendingSummary(BaseModel):
    """Spending analytics summary."""

    period: str  # "weekly", "monthly", "yearly"
    start_date: date
    end_date: date
    total_spending: float
    receipt_count: int
    item_count: int
    categories: list[CategorySpending] = Field(default_factory=list)
    budget_limit: float | None = None
    budget_remaining: float | None = None
    budget_percentage: float | None = None


class PriceComparison(BaseModel):
    """Price comparison for an item across stores."""

    item_name: str
    stores: dict[str, float]  # store -> current price
    cheapest_store: str | None = None
    cheapest_price: float | None = None
    savings: float | None = None  # difference between most and least expensive


class Suggestion(BaseModel):
    """A smart shopping suggestion."""

    type: str  # "restock", "price_alert", "out_of_stock"
    item_name: str
    message: str
    priority: str = "medium"  # high, medium, low
    data: dict[str, Any] = Field(default_factory=dict)


# --- Phase 3 Models ---


class InventoryLocation(str, Enum):
    """Storage locations for inventory items."""

    PANTRY = "pantry"
    FRIDGE = "fridge"
    FREEZER = "freezer"


class WasteReason(str, Enum):
    """Reasons for food waste."""

    SPOILED = "spoiled"
    NEVER_USED = "never_used"
    OVERRIPE = "overripe"
    OTHER = "other"


class InventoryItem(BaseModel):
    """A household inventory item."""

    id: UUID = Field(default_factory=uuid4)
    item_name: str
    category: str = Category.OTHER.value
    quantity: float = 1.0
    unit: str | None = None
    location: InventoryLocation = InventoryLocation.PANTRY
    expiration_date: date | None = None
    opened_date: date | None = None
    low_stock_threshold: float = 1.0
    purchased_date: date = Field(default_factory=date.today)
    receipt_id: UUID | None = None
    added_by: str | None = None

    @property
    def is_expired(self) -> bool:
        """Check if item is expired."""
        if self.expiration_date is None:
            return False
        return self.expiration_date < date.today()

    @property
    def is_low_stock(self) -> bool:
        """Check if item is below threshold."""
        return self.quantity <= self.low_stock_threshold

    @property
    def days_until_expiration(self) -> int | None:
        """Days until expiration."""
        if self.expiration_date is None:
            return None
        return (self.expiration_date - date.today()).days


class WasteRecord(BaseModel):
    """A food waste log entry."""

    id: UUID = Field(default_factory=uuid4)
    item_name: str
    quantity: float = 1.0
    unit: str | None = None
    original_purchase_date: date | None = None
    waste_logged_date: date = Field(default_factory=date.today)
    reason: WasteReason = WasteReason.OTHER
    estimated_cost: float | None = None
    logged_by: str | None = None


class CategoryBudget(BaseModel):
    """Budget allocation for a category."""

    category: str
    limit: float
    spent: float = 0.0

    @property
    def remaining(self) -> float:
        return round(self.limit - self.spent, 2)

    @property
    def percentage_used(self) -> float:
        if self.limit <= 0:
            return 0.0
        return round(self.spent / self.limit * 100, 1)

    @property
    def is_over_budget(self) -> bool:
        return self.spent > self.limit


class BudgetTracking(BaseModel):
    """Monthly budget tracking."""

    month: str  # "YYYY-MM" format
    monthly_limit: float = 0.0
    category_budgets: list[CategoryBudget] = Field(default_factory=list)
    total_spent: float = 0.0

    @property
    def total_remaining(self) -> float:
        return round(self.monthly_limit - self.total_spent, 2)

    @property
    def total_percentage_used(self) -> float:
        if self.monthly_limit <= 0:
            return 0.0
        return round(self.total_spent / self.monthly_limit * 100, 1)
