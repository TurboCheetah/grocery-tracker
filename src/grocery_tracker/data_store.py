"""Data persistence for Grocery Tracker.

This module provides data persistence with support for JSON (default) or SQLite backends.
Use create_data_store() to get the appropriate backend based on configuration.
"""

import json
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from .models import (
    BudgetTracking,
    CategoryBudget,
    FrequencyData,
    GroceryItem,
    GroceryList,
    InventoryItem,
    OutOfStockRecord,
    PriceHistory,
    PricePoint,
    PurchaseRecord,
    Receipt,
    UserPreferences,
    WasteRecord,
)


class BackendType(str, Enum):
    """Data storage backend types."""

    JSON = "json"
    SQLITE = "sqlite"


class DataStoreProtocol(Protocol):
    """Protocol defining the data store interface."""

    def load_list(self) -> GroceryList: ...
    def save_list(self, grocery_list: GroceryList) -> None: ...
    def get_item(self, item_id: UUID) -> GroceryItem | None: ...
    def save_receipt(self, receipt: Receipt) -> UUID: ...
    def load_receipt(self, receipt_id: str | UUID) -> Receipt | None: ...
    def list_receipts(self) -> list[Receipt]: ...
    def load_price_history(self) -> dict[str, dict[str, PriceHistory]]: ...
    def save_price_history(self, history: dict[str, dict[str, PriceHistory]]) -> None: ...
    def update_price(
        self,
        item_name: str,
        store: str,
        price: float,
        purchase_date: date,
        receipt_id: UUID | None = None,
        sale: bool = False,
    ) -> None: ...
    def get_price_history(
        self, item_name: str, store: str | None = None
    ) -> PriceHistory | None: ...
    def load_frequency_data(self) -> dict[str, FrequencyData]: ...
    def save_frequency_data(self, frequency: dict[str, FrequencyData]) -> None: ...
    def update_frequency(
        self,
        item_name: str,
        purchase_date: date,
        quantity: float = 1.0,
        store: str | None = None,
        category: str = "Other",
    ) -> None: ...
    def get_frequency(self, item_name: str) -> FrequencyData | None: ...
    def load_out_of_stock(self) -> list[OutOfStockRecord]: ...
    def save_out_of_stock(self, records: list[OutOfStockRecord]) -> None: ...
    def add_out_of_stock(self, record: OutOfStockRecord) -> UUID: ...
    def get_out_of_stock_for_item(
        self, item_name: str, store: str | None = None
    ) -> list[OutOfStockRecord]: ...
    def load_inventory(self) -> list[InventoryItem]: ...
    def save_inventory(self, items: list[InventoryItem]) -> None: ...
    def load_waste_log(self) -> list[WasteRecord]: ...
    def save_waste_log(self, records: list[WasteRecord]) -> None: ...
    def add_waste_record(self, record: WasteRecord) -> UUID: ...
    def load_budget(self, month: str | None = None) -> BudgetTracking | None: ...
    def save_budget(self, budget: BudgetTracking) -> None: ...
    def load_preferences(self) -> dict[str, UserPreferences]: ...
    def save_preferences(self, preferences: dict[str, UserPreferences]) -> None: ...
    def get_user_preferences(self, user: str) -> UserPreferences | None: ...
    def save_user_preferences(self, prefs: UserPreferences) -> None: ...


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for our data types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.isoformat()
        return super().default(obj)


def json_decoder(data: dict[str, Any]) -> dict[str, Any]:
    """Decode JSON data back to Python objects."""
    for key, value in data.items():
        if isinstance(value, str):
            # Try to parse as UUID
            if key in ("id", "receipt_id", "matched_list_item_id"):
                try:
                    data[key] = UUID(value)
                except ValueError:
                    pass
            # Try to parse as datetime
            elif key in ("added_at", "created_at", "last_updated"):
                try:
                    data[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
            # Try to parse as date
            elif key in ("transaction_date", "date", "recorded_date",
                         "expiration_date", "opened_date", "purchased_date",
                         "original_purchase_date", "waste_logged_date"):
                try:
                    data[key] = date.fromisoformat(value)
                except ValueError:
                    pass
            # Try to parse as time
            elif key == "transaction_time":
                try:
                    data[key] = time.fromisoformat(value)
                except ValueError:
                    pass
    return data


class DataStore:
    """Manages JSON file persistence for grocery data."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize data store.

        Args:
            data_dir: Directory for data files. Defaults to ./data
        """
        self.data_dir = data_dir or Path.cwd() / "data"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "receipts").mkdir(exist_ok=True)
        (self.data_dir / "receipt_images").mkdir(exist_ok=True)

    def _list_path(self) -> Path:
        """Path to current list file."""
        return self.data_dir / "current_list.json"

    def _price_history_path(self) -> Path:
        """Path to price history file."""
        return self.data_dir / "price_history.json"

    def _frequency_data_path(self) -> Path:
        """Path to frequency data file."""
        return self.data_dir / "frequency_data.json"

    def _out_of_stock_path(self) -> Path:
        """Path to out-of-stock records file."""
        return self.data_dir / "out_of_stock.json"

    def _receipt_path(self, receipt_id: str | UUID) -> Path:
        """Path to a receipt file."""
        return self.data_dir / "receipts" / f"{receipt_id}.json"

    # --- Grocery List Operations ---

    def load_list(self) -> GroceryList:
        """Load the current grocery list.

        Returns:
            GroceryList object, empty if file doesn't exist
        """
        path = self._list_path()
        if not path.exists():
            return GroceryList()

        with open(path) as f:
            data = json.load(f, object_hook=json_decoder)

        # Parse items
        items = []
        for item_data in data.get("items", []):
            items.append(GroceryItem(**item_data))

        return GroceryList(
            version=data.get("version", "1.0"),
            last_updated=data.get("last_updated", datetime.now()),
            items=items,
        )

    def save_list(self, grocery_list: GroceryList) -> None:
        """Save the grocery list.

        Args:
            grocery_list: GroceryList to save
        """
        grocery_list.last_updated = datetime.now()
        path = self._list_path()

        with open(path, "w") as f:
            json.dump(grocery_list.model_dump(), f, cls=JSONEncoder, indent=2)

    def get_item(self, item_id: UUID) -> GroceryItem | None:
        """Get a specific item by ID.

        Args:
            item_id: UUID of the item

        Returns:
            GroceryItem if found, None otherwise
        """
        grocery_list = self.load_list()
        for item in grocery_list.items:
            if item.id == item_id:
                return item
        return None

    # --- Receipt Operations ---

    def save_receipt(self, receipt: Receipt) -> UUID:
        """Save a receipt.

        Args:
            receipt: Receipt to save

        Returns:
            Receipt ID
        """
        path = self._receipt_path(receipt.id)

        with open(path, "w") as f:
            json.dump(receipt.model_dump(), f, cls=JSONEncoder, indent=2)

        return receipt.id

    def load_receipt(self, receipt_id: str | UUID) -> Receipt | None:
        """Load a receipt by ID.

        Args:
            receipt_id: Receipt ID

        Returns:
            Receipt if found, None otherwise
        """
        path = self._receipt_path(receipt_id)
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f, object_hook=json_decoder)

        return Receipt(**data)

    def list_receipts(self) -> list[Receipt]:
        """List all receipts.

        Returns:
            List of all receipts
        """
        receipts_dir = self.data_dir / "receipts"
        receipts = []

        for path in receipts_dir.glob("*.json"):
            with open(path) as f:
                data = json.load(f, object_hook=json_decoder)
            receipts.append(Receipt(**data))

        return sorted(receipts, key=lambda r: r.transaction_date, reverse=True)

    # --- Price History Operations ---

    def load_price_history(self) -> dict[str, dict[str, PriceHistory]]:
        """Load price history.

        Returns:
            Dict mapping item_name -> store -> PriceHistory
        """
        path = self._price_history_path()
        if not path.exists():
            return {}

        with open(path) as f:
            data = json.load(f, object_hook=json_decoder)

        result: dict[str, dict[str, PriceHistory]] = {}
        for item_name, stores in data.items():
            result[item_name] = {}
            for store_name, history_data in stores.items():
                price_points = [PricePoint(**pp) for pp in history_data.get("price_points", [])]
                result[item_name][store_name] = PriceHistory(
                    item_name=item_name,
                    store=store_name,
                    price_points=price_points,
                )

        return result

    def save_price_history(self, history: dict[str, dict[str, PriceHistory]]) -> None:
        """Save price history.

        Args:
            history: Dict mapping item_name -> store -> PriceHistory
        """
        path = self._price_history_path()

        data = {}
        for item_name, stores in history.items():
            data[item_name] = {}
            for store_name, price_history in stores.items():
                data[item_name][store_name] = price_history.model_dump()

        with open(path, "w") as f:
            json.dump(data, f, cls=JSONEncoder, indent=2)

    def update_price(
        self,
        item_name: str,
        store: str,
        price: float,
        purchase_date: date,
        receipt_id: UUID | None = None,
        sale: bool = False,
    ) -> None:
        """Update price history for an item.

        Args:
            item_name: Name of the item
            store: Store name
            price: Price observed
            purchase_date: Date of purchase
            receipt_id: Optional receipt ID
            sale: Whether this was a sale price
        """
        history = self.load_price_history()

        if item_name not in history:
            history[item_name] = {}

        if store not in history[item_name]:
            history[item_name][store] = PriceHistory(item_name=item_name, store=store)

        history[item_name][store].price_points.append(
            PricePoint(
                date=purchase_date,
                price=price,
                sale=sale,
                receipt_id=receipt_id,
            )
        )

        self.save_price_history(history)

    def get_price_history(self, item_name: str, store: str | None = None) -> PriceHistory | None:
        """Get price history for an item.

        Args:
            item_name: Name of the item
            store: Optional store to filter by

        Returns:
            PriceHistory if found, None otherwise
        """
        history = self.load_price_history()

        if item_name not in history:
            return None

        if store:
            return history[item_name].get(store)

        # Combine all stores
        all_points = []
        for store_history in history[item_name].values():
            all_points.extend(store_history.price_points)

        if not all_points:
            return None

        return PriceHistory(
            item_name=item_name,
            store="all",
            price_points=sorted(all_points, key=lambda p: p.date),
        )

    # --- Frequency Data Operations ---

    def load_frequency_data(self) -> dict[str, FrequencyData]:
        """Load frequency data for all items.

        Returns:
            Dict mapping item_name -> FrequencyData
        """
        path = self._frequency_data_path()
        if not path.exists():
            return {}

        with open(path) as f:
            data = json.load(f, object_hook=json_decoder)

        result: dict[str, FrequencyData] = {}
        for item_name, freq_data in data.items():
            purchases = [
                PurchaseRecord(**p) for p in freq_data.get("purchase_history", [])
            ]
            result[item_name] = FrequencyData(
                item_name=item_name,
                category=freq_data.get("category", "Other"),
                purchase_history=purchases,
            )

        return result

    def save_frequency_data(self, frequency: dict[str, FrequencyData]) -> None:
        """Save frequency data.

        Args:
            frequency: Dict mapping item_name -> FrequencyData
        """
        path = self._frequency_data_path()

        data = {}
        for item_name, freq in frequency.items():
            data[item_name] = freq.model_dump()

        with open(path, "w") as f:
            json.dump(data, f, cls=JSONEncoder, indent=2)

    def update_frequency(
        self,
        item_name: str,
        purchase_date: date,
        quantity: float = 1.0,
        store: str | None = None,
        category: str = "Other",
    ) -> None:
        """Record a purchase for frequency tracking.

        Args:
            item_name: Name of the item
            purchase_date: Date of purchase
            quantity: Quantity bought
            store: Store where purchased
            category: Item category
        """
        frequency = self.load_frequency_data()

        if item_name not in frequency:
            frequency[item_name] = FrequencyData(
                item_name=item_name, category=category
            )

        frequency[item_name].purchase_history.append(
            PurchaseRecord(date=purchase_date, quantity=quantity, store=store)
        )

        self.save_frequency_data(frequency)

    def get_frequency(self, item_name: str) -> FrequencyData | None:
        """Get frequency data for a specific item.

        Args:
            item_name: Name of the item

        Returns:
            FrequencyData if found, None otherwise
        """
        frequency = self.load_frequency_data()
        return frequency.get(item_name)

    # --- Out of Stock Operations ---

    def load_out_of_stock(self) -> list[OutOfStockRecord]:
        """Load all out-of-stock records.

        Returns:
            List of OutOfStockRecord
        """
        path = self._out_of_stock_path()
        if not path.exists():
            return []

        with open(path) as f:
            data = json.load(f, object_hook=json_decoder)

        return [OutOfStockRecord(**record) for record in data]

    def save_out_of_stock(self, records: list[OutOfStockRecord]) -> None:
        """Save out-of-stock records.

        Args:
            records: List of OutOfStockRecord
        """
        path = self._out_of_stock_path()

        with open(path, "w") as f:
            json.dump(
                [r.model_dump() for r in records], f, cls=JSONEncoder, indent=2
            )

    def add_out_of_stock(self, record: OutOfStockRecord) -> UUID:
        """Add an out-of-stock record.

        Args:
            record: OutOfStockRecord to add

        Returns:
            Record ID
        """
        records = self.load_out_of_stock()
        records.append(record)
        self.save_out_of_stock(records)
        return record.id

    def get_out_of_stock_for_item(
        self, item_name: str, store: str | None = None
    ) -> list[OutOfStockRecord]:
        """Get out-of-stock records for an item.

        Args:
            item_name: Item name to filter by
            store: Optional store to filter by

        Returns:
            List of matching OutOfStockRecord
        """
        records = self.load_out_of_stock()
        filtered = [
            r for r in records if r.item_name.lower() == item_name.lower()
        ]
        if store:
            filtered = [r for r in filtered if r.store.lower() == store.lower()]
        return filtered

    # --- Inventory Operations ---

    def _inventory_path(self) -> Path:
        """Path to inventory file."""
        return self.data_dir / "inventory.json"

    def load_inventory(self) -> list[InventoryItem]:
        """Load inventory items.

        Returns:
            List of InventoryItem
        """
        path = self._inventory_path()
        if not path.exists():
            return []

        with open(path) as f:
            data = json.load(f, object_hook=json_decoder)

        return [InventoryItem(**item) for item in data]

    def save_inventory(self, items: list[InventoryItem]) -> None:
        """Save inventory items.

        Args:
            items: List of InventoryItem to save
        """
        path = self._inventory_path()

        with open(path, "w") as f:
            json.dump(
                [i.model_dump() for i in items], f, cls=JSONEncoder, indent=2
            )

    # --- Waste Log Operations ---

    def _waste_log_path(self) -> Path:
        """Path to waste log file."""
        return self.data_dir / "waste_log.json"

    def load_waste_log(self) -> list[WasteRecord]:
        """Load waste log records.

        Returns:
            List of WasteRecord
        """
        path = self._waste_log_path()
        if not path.exists():
            return []

        with open(path) as f:
            data = json.load(f, object_hook=json_decoder)

        return [WasteRecord(**record) for record in data]

    def save_waste_log(self, records: list[WasteRecord]) -> None:
        """Save waste log records.

        Args:
            records: List of WasteRecord to save
        """
        path = self._waste_log_path()

        with open(path, "w") as f:
            json.dump(
                [r.model_dump() for r in records], f, cls=JSONEncoder, indent=2
            )

    def add_waste_record(self, record: WasteRecord) -> UUID:
        """Add a waste record.

        Args:
            record: WasteRecord to add

        Returns:
            Record ID
        """
        records = self.load_waste_log()
        records.append(record)
        self.save_waste_log(records)
        return record.id

    # --- Budget Operations ---

    def _budget_path(self) -> Path:
        """Path to budget file."""
        return self.data_dir / "budget.json"

    def load_budget(self, month: str | None = None) -> BudgetTracking | None:
        """Load budget tracking for a month.

        Args:
            month: Month in YYYY-MM format. Defaults to current month.

        Returns:
            BudgetTracking or None
        """
        if month is None:
            month = date.today().strftime("%Y-%m")

        path = self._budget_path()
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        budgets = data if isinstance(data, dict) else {}
        if month not in budgets:
            return None

        budget_data = budgets[month]
        cat_budgets = [
            CategoryBudget(**cb) for cb in budget_data.get("category_budgets", [])
        ]
        return BudgetTracking(
            month=month,
            monthly_limit=budget_data.get("monthly_limit", 0.0),
            category_budgets=cat_budgets,
            total_spent=budget_data.get("total_spent", 0.0),
        )

    def save_budget(self, budget: BudgetTracking) -> None:
        """Save budget tracking.

        Args:
            budget: BudgetTracking to save
        """
        path = self._budget_path()

        if path.exists():
            with open(path) as f:
                all_budgets = json.load(f)
        else:
            all_budgets = {}

        all_budgets[budget.month] = budget.model_dump()

        with open(path, "w") as f:
            json.dump(all_budgets, f, cls=JSONEncoder, indent=2)

    # --- User Preferences Operations ---

    def _preferences_path(self) -> Path:
        """Path to user preferences file."""
        return self.data_dir / "user_preferences.json"

    def load_preferences(self) -> dict[str, UserPreferences]:
        """Load all user preferences.

        Returns:
            Dict mapping username -> UserPreferences
        """
        path = self._preferences_path()
        if not path.exists():
            return {}

        with open(path) as f:
            data = json.load(f)

        return {
            name: UserPreferences(**prefs) for name, prefs in data.items()
        }

    def save_preferences(self, preferences: dict[str, UserPreferences]) -> None:
        """Save user preferences.

        Args:
            preferences: Dict mapping username -> UserPreferences
        """
        path = self._preferences_path()

        with open(path, "w") as f:
            json.dump(
                {name: prefs.model_dump() for name, prefs in preferences.items()},
                f,
                cls=JSONEncoder,
                indent=2,
            )

    def get_user_preferences(self, user: str) -> UserPreferences | None:
        """Get preferences for a specific user.

        Args:
            user: Username

        Returns:
            UserPreferences or None
        """
        prefs = self.load_preferences()
        return prefs.get(user)

    def save_user_preferences(self, prefs: UserPreferences) -> None:
        """Save preferences for a user.

        Args:
            prefs: UserPreferences to save
        """
        all_prefs = self.load_preferences()
        all_prefs[prefs.user] = prefs
        self.save_preferences(all_prefs)


def create_data_store(
    backend: BackendType = BackendType.JSON,
    data_dir: Path | None = None,
    db_path: Path | None = None,
) -> DataStoreProtocol:
    """Create a data store with the specified backend.

    Args:
        backend: Which backend to use (json or sqlite)
        data_dir: Directory for data files (used by JSON backend, also used
                  as base path for SQLite if db_path not specified)
        db_path: Path to SQLite database file (only used by SQLite backend)

    Returns:
        A DataStore or SQLiteStore instance

    Example:
        # Use JSON backend (default)
        store = create_data_store()

        # Use SQLite backend
        store = create_data_store(BackendType.SQLITE)

        # Use SQLite with custom path
        store = create_data_store(
            BackendType.SQLITE,
            db_path=Path("./my_data/grocery.db")
        )
    """
    if backend == BackendType.SQLITE:
        from .sqlite_store import SQLiteStore

        if db_path is None and data_dir is not None:
            db_path = data_dir / "grocery.db"

        return SQLiteStore(db_path=db_path)
    else:
        return DataStore(data_dir=data_dir)
