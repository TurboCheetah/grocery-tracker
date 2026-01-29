"""Grocery Tracker - Intelligent grocery list and inventory management."""

from .analytics import Analytics
from .config import ConfigManager
from .data_store import BackendType, create_data_store, DataStore
from .inventory_manager import InventoryManager
from .sqlite_store import SQLiteStore
from .list_manager import DuplicateItemError, ItemNotFoundError, ListManager
from .models import (
    BudgetTracking,
    Category,
    CategoryBudget,
    CategorySpending,
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
    ReconciliationResult,
    SpendingSummary,
    Suggestion,
    UserPreferences,
    WasteReason,
    WasteRecord,
)
from .output_formatter import OutputFormatter
from .receipt_processor import ReceiptInput, ReceiptProcessor

__version__ = "0.1.0"

__all__ = [
    "Analytics",
    "BackendType",
    "BudgetTracking",
    "Category",
    "CategoryBudget",
    "CategorySpending",
    "ConfigManager",
    "create_data_store",
    "DataStore",
    "DuplicateItemError",
    "FrequencyData",
    "GroceryItem",
    "GroceryList",
    "InventoryItem",
    "InventoryLocation",
    "InventoryManager",
    "ItemNotFoundError",
    "ItemStatus",
    "LineItem",
    "ListManager",
    "OutOfStockRecord",
    "OutputFormatter",
    "PriceComparison",
    "PriceHistory",
    "PricePoint",
    "Priority",
    "PurchaseRecord",
    "Receipt",
    "ReceiptInput",
    "ReceiptProcessor",
    "ReconciliationResult",
    "SpendingSummary",
    "SQLiteStore",
    "Suggestion",
    "UserPreferences",
    "WasteReason",
    "WasteRecord",
]
