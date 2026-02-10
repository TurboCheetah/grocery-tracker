"""SQLite-based data persistence for Grocery Tracker.

This module provides SQLite database storage as an alternative to JSON files.
It implements the same interface as DataStore for seamless switching.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
from uuid import UUID

from .item_normalizer import normalize_item_name
from .models import (
    BudgetTracking,
    CategoryBudget,
    FrequencyData,
    GroceryItem,
    GroceryList,
    InventoryItem,
    InventoryLocation,
    ItemStatus,
    LineItem,
    OutOfStockRecord,
    PriceHistory,
    PricePoint,
    Priority,
    PurchaseRecord,
    Receipt,
    UserPreferences,
    WasteReason,
    WasteRecord,
)


def adapt_uuid(uuid_val: UUID) -> str:
    """Adapt UUID to string for SQLite."""
    return str(uuid_val)


def convert_uuid(value: bytes) -> UUID:
    """Convert string back to UUID from SQLite."""
    return UUID(value.decode())


def adapt_datetime(dt: datetime) -> str:
    """Adapt datetime to ISO string for SQLite."""
    return dt.isoformat()


def convert_datetime(value: bytes) -> datetime:
    """Convert ISO string back to datetime from SQLite."""
    return datetime.fromisoformat(value.decode())


def adapt_date(d: date) -> str:
    """Adapt date to ISO string for SQLite."""
    return d.isoformat()


def convert_date(value: bytes) -> date:
    """Convert ISO string back to date from SQLite."""
    return date.fromisoformat(value.decode())


def adapt_time(t: time) -> str:
    """Adapt time to ISO string for SQLite."""
    return t.isoformat()


def convert_time(value: bytes) -> time:
    """Convert ISO string back to time from SQLite."""
    return time.fromisoformat(value.decode())


# Register adapters and converters
sqlite3.register_adapter(UUID, adapt_uuid)
sqlite3.register_converter("UUID", convert_uuid)
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("DATETIME", convert_datetime)
sqlite3.register_adapter(date, adapt_date)
sqlite3.register_converter("DATE", convert_date)
sqlite3.register_adapter(time, adapt_time)
sqlite3.register_converter("TIME", convert_time)


class SQLiteStore:
    """Manages SQLite database persistence for grocery data."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Path | None = None):
        """Initialize SQLite store.

        Args:
            db_path: Path to the SQLite database file. Defaults to ./data/grocery.db
        """
        if db_path is None:
            db_path = Path.cwd() / "data" / "grocery.db"
        self.db_path = db_path
        self._ensure_directories()
        self._init_database()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Also create receipt_images directory for compatibility
        (self.db_path.parent / "receipt_images").mkdir(exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Initialize database schema if not exists."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Schema version tracking
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );

                -- Shopping list items
                CREATE TABLE IF NOT EXISTS grocery_items (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    unit TEXT,
                    category TEXT NOT NULL DEFAULT 'Other',
                    store TEXT,
                    aisle TEXT,
                    brand_preference TEXT,
                    estimated_price REAL,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    added_by TEXT,
                    added_at TEXT NOT NULL,
                    notes TEXT,
                    status TEXT NOT NULL DEFAULT 'to_buy'
                );

                -- List metadata
                CREATE TABLE IF NOT EXISTS list_metadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version TEXT NOT NULL DEFAULT '1.0',
                    last_updated TEXT NOT NULL
                );

                -- Receipts
                CREATE TABLE IF NOT EXISTS receipts (
                    id TEXT PRIMARY KEY,
                    store_name TEXT NOT NULL,
                    store_location TEXT,
                    transaction_date TEXT NOT NULL,
                    transaction_time TEXT,
                    purchased_by TEXT,
                    subtotal REAL NOT NULL,
                    tax REAL NOT NULL DEFAULT 0.0,
                    total REAL NOT NULL,
                    payment_method TEXT,
                    receipt_image_path TEXT,
                    raw_ocr_text TEXT,
                    created_at TEXT NOT NULL
                );

                -- Receipt line items
                CREATE TABLE IF NOT EXISTS receipt_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id TEXT NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
                    item_name TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 1.0,
                    unit_price REAL NOT NULL,
                    total_price REAL NOT NULL,
                    matched_list_item_id TEXT REFERENCES grocery_items(id)
                );

                -- Price history
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    store TEXT NOT NULL,
                    price REAL NOT NULL,
                    unit TEXT,
                    date TEXT NOT NULL,
                    sale INTEGER NOT NULL DEFAULT 0,
                    receipt_id TEXT REFERENCES receipts(id)
                );

                -- Create index for price history lookups
                CREATE INDEX IF NOT EXISTS idx_price_history_item_store
                    ON price_history(item_name, store);

                -- Purchase frequency tracking
                CREATE TABLE IF NOT EXISTS frequency_data (
                    item_name TEXT PRIMARY KEY,
                    category TEXT NOT NULL DEFAULT 'Other'
                );

                -- Purchase records for frequency tracking
                CREATE TABLE IF NOT EXISTS purchase_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL REFERENCES frequency_data(item_name) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 1.0,
                    store TEXT
                );

                -- Out of stock records
                CREATE TABLE IF NOT EXISTS out_of_stock (
                    id TEXT PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    store TEXT NOT NULL,
                    recorded_date TEXT NOT NULL,
                    substitution TEXT,
                    reported_by TEXT
                );

                -- Inventory items
                CREATE TABLE IF NOT EXISTS inventory (
                    id TEXT PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Other',
                    quantity REAL NOT NULL DEFAULT 1.0,
                    unit TEXT,
                    location TEXT NOT NULL DEFAULT 'pantry',
                    expiration_date TEXT,
                    opened_date TEXT,
                    low_stock_threshold REAL NOT NULL DEFAULT 1.0,
                    purchased_date TEXT NOT NULL,
                    receipt_id TEXT REFERENCES receipts(id),
                    added_by TEXT
                );

                -- Waste log
                CREATE TABLE IF NOT EXISTS waste_log (
                    id TEXT PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 1.0,
                    unit TEXT,
                    original_purchase_date TEXT,
                    waste_logged_date TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT 'other',
                    estimated_cost REAL,
                    logged_by TEXT
                );

                -- Budget tracking
                CREATE TABLE IF NOT EXISTS budgets (
                    month TEXT PRIMARY KEY,
                    monthly_limit REAL NOT NULL DEFAULT 0.0,
                    total_spent REAL NOT NULL DEFAULT 0.0
                );

                -- Category budgets
                CREATE TABLE IF NOT EXISTS category_budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month TEXT NOT NULL REFERENCES budgets(month) ON DELETE CASCADE,
                    category TEXT NOT NULL,
                    limit_amount REAL NOT NULL,
                    spent REAL NOT NULL DEFAULT 0.0,
                    UNIQUE(month, category)
                );

                -- User preferences
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_name TEXT PRIMARY KEY,
                    brand_preferences TEXT NOT NULL DEFAULT '{}',
                    dietary_restrictions TEXT NOT NULL DEFAULT '[]',
                    allergens TEXT NOT NULL DEFAULT '[]',
                    favorite_items TEXT NOT NULL DEFAULT '[]',
                    shopping_patterns TEXT NOT NULL DEFAULT '{}'
                );

                -- Initialize list metadata if not exists
                INSERT OR IGNORE INTO list_metadata (id, version, last_updated)
                VALUES (1, '1.0', datetime('now'));

                -- Record schema version
                INSERT OR IGNORE INTO schema_version (version) VALUES (1);
            """)

    # --- Grocery List Operations ---

    def load_list(self) -> GroceryList:
        """Load the current grocery list.

        Returns:
            GroceryList object
        """
        with self._get_connection() as conn:
            # Load metadata
            meta_row = conn.execute(
                "SELECT version, last_updated FROM list_metadata WHERE id = 1"
            ).fetchone()

            version = meta_row["version"] if meta_row else "1.0"
            last_updated_str = meta_row["last_updated"] if meta_row else datetime.now().isoformat()
            last_updated = datetime.fromisoformat(last_updated_str)

            # Load items
            rows = conn.execute("SELECT * FROM grocery_items ORDER BY added_at DESC").fetchall()

            items = []
            for row in rows:
                items.append(
                    GroceryItem(
                        id=UUID(row["id"]),
                        name=row["name"],
                        quantity=self._parse_quantity(row["quantity"]),
                        unit=row["unit"],
                        category=row["category"],
                        store=row["store"],
                        aisle=row["aisle"],
                        brand_preference=row["brand_preference"],
                        estimated_price=row["estimated_price"],
                        priority=Priority(row["priority"]),
                        added_by=row["added_by"],
                        added_at=datetime.fromisoformat(row["added_at"]),
                        notes=row["notes"],
                        status=ItemStatus(row["status"]),
                    )
                )

            return GroceryList(
                version=version,
                last_updated=last_updated,
                items=items,
            )

    def _parse_quantity(self, quantity_str: str) -> int | float | str:
        """Parse quantity from string stored in database."""
        try:
            # Try as int first
            val = int(quantity_str)
            return val
        except ValueError:
            try:
                # Try as float
                val = float(quantity_str)
                return val
            except ValueError:
                # Keep as string
                return quantity_str

    def save_list(self, grocery_list: GroceryList) -> None:
        """Save the grocery list.

        Args:
            grocery_list: GroceryList to save
        """
        grocery_list.last_updated = datetime.now()

        with self._get_connection() as conn:
            # Update metadata
            conn.execute(
                """
                UPDATE list_metadata
                SET version = ?, last_updated = ?
                WHERE id = 1
                """,
                (grocery_list.version, grocery_list.last_updated.isoformat()),
            )

            # Get existing item IDs
            existing_ids = {
                row["id"] for row in conn.execute("SELECT id FROM grocery_items").fetchall()
            }

            # Get new item IDs
            new_ids = {str(item.id) for item in grocery_list.items}

            # Delete removed items
            removed_ids = existing_ids - new_ids
            if removed_ids:
                placeholders = ",".join("?" * len(removed_ids))
                conn.execute(
                    f"DELETE FROM grocery_items WHERE id IN ({placeholders})",
                    list(removed_ids),
                )

            # Upsert items
            for item in grocery_list.items:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO grocery_items
                    (id, name, quantity, unit, category, store, aisle, brand_preference,
                     estimated_price, priority, added_by, added_at, notes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.id),
                        item.name,
                        str(item.quantity),
                        item.unit,
                        item.category,
                        item.store,
                        item.aisle,
                        item.brand_preference,
                        item.estimated_price,
                        item.priority.value,
                        item.added_by,
                        item.added_at.isoformat(),
                        item.notes,
                        item.status.value,
                    ),
                )

    def get_item(self, item_id: UUID) -> GroceryItem | None:
        """Get a specific item by ID.

        Args:
            item_id: UUID of the item

        Returns:
            GroceryItem if found, None otherwise
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM grocery_items WHERE id = ?",
                (str(item_id),),
            ).fetchone()

            if not row:
                return None

            return GroceryItem(
                id=UUID(row["id"]),
                name=row["name"],
                quantity=self._parse_quantity(row["quantity"]),
                unit=row["unit"],
                category=row["category"],
                store=row["store"],
                aisle=row["aisle"],
                brand_preference=row["brand_preference"],
                estimated_price=row["estimated_price"],
                priority=Priority(row["priority"]),
                added_by=row["added_by"],
                added_at=datetime.fromisoformat(row["added_at"]),
                notes=row["notes"],
                status=ItemStatus(row["status"]),
            )

    # --- Receipt Operations ---

    def save_receipt(self, receipt: Receipt) -> UUID:
        """Save a receipt.

        Args:
            receipt: Receipt to save

        Returns:
            Receipt ID
        """
        with self._get_connection() as conn:
            # Insert receipt
            conn.execute(
                """
                INSERT OR REPLACE INTO receipts
                (id, store_name, store_location, transaction_date, transaction_time,
                 purchased_by, subtotal, tax, total, payment_method, receipt_image_path,
                 raw_ocr_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(receipt.id),
                    receipt.store_name,
                    receipt.store_location,
                    receipt.transaction_date.isoformat(),
                    receipt.transaction_time.isoformat() if receipt.transaction_time else None,
                    receipt.purchased_by,
                    receipt.subtotal,
                    receipt.tax,
                    receipt.total,
                    receipt.payment_method,
                    receipt.receipt_image_path,
                    receipt.raw_ocr_text,
                    receipt.created_at.isoformat(),
                ),
            )

            # Delete existing line items for this receipt
            conn.execute(
                "DELETE FROM receipt_items WHERE receipt_id = ?",
                (str(receipt.id),),
            )

            # Insert line items
            for item in receipt.line_items:
                conn.execute(
                    """
                    INSERT INTO receipt_items
                    (receipt_id, item_name, quantity, unit_price, total_price, matched_list_item_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(receipt.id),
                        item.item_name,
                        item.quantity,
                        item.unit_price,
                        item.total_price,
                        str(item.matched_list_item_id) if item.matched_list_item_id else None,
                    ),
                )

        return receipt.id

    def load_receipt(self, receipt_id: str | UUID) -> Receipt | None:
        """Load a receipt by ID.

        Args:
            receipt_id: Receipt ID

        Returns:
            Receipt if found, None otherwise
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM receipts WHERE id = ?",
                (str(receipt_id),),
            ).fetchone()

            if not row:
                return None

            # Load line items
            item_rows = conn.execute(
                "SELECT * FROM receipt_items WHERE receipt_id = ?",
                (str(receipt_id),),
            ).fetchall()

            line_items = [
                LineItem(
                    item_name=item_row["item_name"],
                    quantity=item_row["quantity"],
                    unit_price=item_row["unit_price"],
                    total_price=item_row["total_price"],
                    matched_list_item_id=UUID(item_row["matched_list_item_id"])
                    if item_row["matched_list_item_id"]
                    else None,
                )
                for item_row in item_rows
            ]

            return Receipt(
                id=UUID(row["id"]),
                store_name=row["store_name"],
                store_location=row["store_location"],
                transaction_date=date.fromisoformat(row["transaction_date"]),
                transaction_time=time.fromisoformat(row["transaction_time"])
                if row["transaction_time"]
                else None,
                purchased_by=row["purchased_by"],
                line_items=line_items,
                subtotal=row["subtotal"],
                tax=row["tax"],
                total=row["total"],
                payment_method=row["payment_method"],
                receipt_image_path=row["receipt_image_path"],
                raw_ocr_text=row["raw_ocr_text"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_receipts(self) -> list[Receipt]:
        """List all receipts.

        Returns:
            List of all receipts sorted by transaction date (most recent first)
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id FROM receipts ORDER BY transaction_date DESC").fetchall()

            receipts = []
            for row in rows:
                receipt = self.load_receipt(row["id"])
                if receipt:
                    receipts.append(receipt)

            return receipts

    # --- Price History Operations ---

    def load_price_history(self) -> dict[str, dict[str, PriceHistory]]:
        """Load price history.

        Returns:
            Dict mapping item_name -> store -> PriceHistory
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM price_history ORDER BY date").fetchall()

            result: dict[str, dict[str, PriceHistory]] = {}
            for row in rows:
                item_name = row["item_name"]
                store = row["store"]

                if item_name not in result:
                    result[item_name] = {}

                if store not in result[item_name]:
                    result[item_name][store] = PriceHistory(
                        item_name=item_name,
                        store=store,
                    )

                result[item_name][store].price_points.append(
                    PricePoint(
                        date=date.fromisoformat(row["date"]),
                        price=row["price"],
                        unit=row["unit"],
                        sale=bool(row["sale"]),
                        receipt_id=UUID(row["receipt_id"]) if row["receipt_id"] else None,
                    )
                )

            return result

    def save_price_history(self, history: dict[str, dict[str, PriceHistory]]) -> None:
        """Save price history.

        Args:
            history: Dict mapping item_name -> store -> PriceHistory
        """
        with self._get_connection() as conn:
            # Clear existing price history
            conn.execute("DELETE FROM price_history")

            # Insert all price points
            for item_name, stores in history.items():
                for store_name, price_history in stores.items():
                    for point in price_history.price_points:
                        conn.execute(
                            """
                            INSERT INTO price_history
                            (item_name, store, price, unit, date, sale, receipt_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item_name,
                                store_name,
                                point.price,
                                point.unit,
                                point.date.isoformat(),
                                1 if point.sale else 0,
                                str(point.receipt_id) if point.receipt_id else None,
                            ),
                        )

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
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO price_history
                (item_name, store, price, date, sale, receipt_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item_name,
                    store,
                    price,
                    purchase_date.isoformat(),
                    1 if sale else 0,
                    str(receipt_id) if receipt_id else None,
                ),
            )

    def get_price_history(self, item_name: str, store: str | None = None) -> PriceHistory | None:
        """Get price history for an item.

        Args:
            item_name: Name of the item
            store: Optional store to filter by

        Returns:
            PriceHistory if found, None otherwise
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM price_history
                ORDER BY date
                """
            ).fetchall()

            canonical_target = normalize_item_name(item_name)
            matched_rows = [
                row
                for row in rows
                if normalize_item_name(row["item_name"]) == canonical_target
                and (store is None or row["store"] == store)
            ]

            if not matched_rows:
                return None

            first_name = matched_rows[0]["item_name"]
            price_points = [
                PricePoint(
                    date=date.fromisoformat(row["date"]),
                    price=row["price"],
                    unit=row["unit"],
                    sale=bool(row["sale"]),
                    receipt_id=UUID(row["receipt_id"]) if row["receipt_id"] else None,
                )
                for row in matched_rows
            ]

            return PriceHistory(
                item_name=first_name,
                store=store or "all",
                price_points=price_points,
            )

    # --- Frequency Data Operations ---

    def load_frequency_data(self) -> dict[str, FrequencyData]:
        """Load frequency data for all items.

        Returns:
            Dict mapping item_name -> FrequencyData
        """
        with self._get_connection() as conn:
            freq_rows = conn.execute("SELECT * FROM frequency_data").fetchall()

            result: dict[str, FrequencyData] = {}
            for freq_row in freq_rows:
                item_name = freq_row["item_name"]

                # Load purchase records for this item
                record_rows = conn.execute(
                    """
                    SELECT * FROM purchase_records
                    WHERE item_name = ?
                    ORDER BY date
                    """,
                    (item_name,),
                ).fetchall()

                purchase_history = [
                    PurchaseRecord(
                        date=date.fromisoformat(row["date"]),
                        quantity=row["quantity"],
                        store=row["store"],
                    )
                    for row in record_rows
                ]

                result[item_name] = FrequencyData(
                    item_name=item_name,
                    category=freq_row["category"],
                    purchase_history=purchase_history,
                )

            return result

    def save_frequency_data(self, frequency: dict[str, FrequencyData]) -> None:
        """Save frequency data.

        Args:
            frequency: Dict mapping item_name -> FrequencyData
        """
        with self._get_connection() as conn:
            # Clear existing data
            conn.execute("DELETE FROM purchase_records")
            conn.execute("DELETE FROM frequency_data")

            # Insert all frequency data
            for item_name, freq in frequency.items():
                conn.execute(
                    """
                    INSERT INTO frequency_data (item_name, category)
                    VALUES (?, ?)
                    """,
                    (item_name, freq.category),
                )

                for record in freq.purchase_history:
                    conn.execute(
                        """
                        INSERT INTO purchase_records
                        (item_name, date, quantity, store)
                        VALUES (?, ?, ?, ?)
                        """,
                        (item_name, record.date.isoformat(), record.quantity, record.store),
                    )

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
        with self._get_connection() as conn:
            # Ensure frequency_data entry exists
            conn.execute(
                """
                INSERT OR IGNORE INTO frequency_data (item_name, category)
                VALUES (?, ?)
                """,
                (item_name, category),
            )

            # Add purchase record
            conn.execute(
                """
                INSERT INTO purchase_records (item_name, date, quantity, store)
                VALUES (?, ?, ?, ?)
                """,
                (item_name, purchase_date.isoformat(), quantity, store),
            )

    def get_frequency(self, item_name: str) -> FrequencyData | None:
        """Get frequency data for a specific item.

        Args:
            item_name: Name of the item

        Returns:
            FrequencyData if found, None otherwise
        """
        with self._get_connection() as conn:
            freq_row = conn.execute(
                "SELECT * FROM frequency_data WHERE item_name = ?",
                (item_name,),
            ).fetchone()

            if not freq_row:
                return None

            record_rows = conn.execute(
                """
                SELECT * FROM purchase_records
                WHERE item_name = ?
                ORDER BY date
                """,
                (item_name,),
            ).fetchall()

            return FrequencyData(
                item_name=item_name,
                category=freq_row["category"],
                purchase_history=[
                    PurchaseRecord(
                        date=date.fromisoformat(row["date"]),
                        quantity=row["quantity"],
                        store=row["store"],
                    )
                    for row in record_rows
                ],
            )

    # --- Out of Stock Operations ---

    def load_out_of_stock(self) -> list[OutOfStockRecord]:
        """Load all out-of-stock records.

        Returns:
            List of OutOfStockRecord
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM out_of_stock ORDER BY recorded_date DESC").fetchall()

            return [
                OutOfStockRecord(
                    id=UUID(row["id"]),
                    item_name=row["item_name"],
                    store=row["store"],
                    recorded_date=date.fromisoformat(row["recorded_date"]),
                    substitution=row["substitution"],
                    reported_by=row["reported_by"],
                )
                for row in rows
            ]

    def save_out_of_stock(self, records: list[OutOfStockRecord]) -> None:
        """Save out-of-stock records.

        Args:
            records: List of OutOfStockRecord
        """
        with self._get_connection() as conn:
            # Clear existing records
            conn.execute("DELETE FROM out_of_stock")

            # Insert all records
            for record in records:
                conn.execute(
                    """
                    INSERT INTO out_of_stock
                    (id, item_name, store, recorded_date, substitution, reported_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(record.id),
                        record.item_name,
                        record.store,
                        record.recorded_date.isoformat(),
                        record.substitution,
                        record.reported_by,
                    ),
                )

    def add_out_of_stock(self, record: OutOfStockRecord) -> UUID:
        """Add an out-of-stock record.

        Args:
            record: OutOfStockRecord to add

        Returns:
            Record ID
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO out_of_stock
                (id, item_name, store, recorded_date, substitution, reported_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.id),
                    record.item_name,
                    record.store,
                    record.recorded_date.isoformat(),
                    record.substitution,
                    record.reported_by,
                ),
            )

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
        with self._get_connection() as conn:
            if store:
                rows = conn.execute(
                    """
                    SELECT * FROM out_of_stock
                    WHERE LOWER(item_name) = LOWER(?) AND LOWER(store) = LOWER(?)
                    ORDER BY recorded_date DESC
                    """,
                    (item_name, store),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM out_of_stock
                    WHERE LOWER(item_name) = LOWER(?)
                    ORDER BY recorded_date DESC
                    """,
                    (item_name,),
                ).fetchall()

            return [
                OutOfStockRecord(
                    id=UUID(row["id"]),
                    item_name=row["item_name"],
                    store=row["store"],
                    recorded_date=date.fromisoformat(row["recorded_date"]),
                    substitution=row["substitution"],
                    reported_by=row["reported_by"],
                )
                for row in rows
            ]

    # --- Inventory Operations ---

    def load_inventory(self) -> list[InventoryItem]:
        """Load inventory items.

        Returns:
            List of InventoryItem
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM inventory ORDER BY item_name").fetchall()

            return [
                InventoryItem(
                    id=UUID(row["id"]),
                    item_name=row["item_name"],
                    category=row["category"],
                    quantity=row["quantity"],
                    unit=row["unit"],
                    location=InventoryLocation(row["location"]),
                    expiration_date=date.fromisoformat(row["expiration_date"])
                    if row["expiration_date"]
                    else None,
                    opened_date=date.fromisoformat(row["opened_date"])
                    if row["opened_date"]
                    else None,
                    low_stock_threshold=row["low_stock_threshold"],
                    purchased_date=date.fromisoformat(row["purchased_date"]),
                    receipt_id=UUID(row["receipt_id"]) if row["receipt_id"] else None,
                    added_by=row["added_by"],
                )
                for row in rows
            ]

    def save_inventory(self, items: list[InventoryItem]) -> None:
        """Save inventory items.

        Args:
            items: List of InventoryItem to save
        """
        with self._get_connection() as conn:
            # Clear existing inventory
            conn.execute("DELETE FROM inventory")

            # Insert all items
            for item in items:
                conn.execute(
                    """
                    INSERT INTO inventory
                    (id, item_name, category, quantity, unit, location, expiration_date,
                     opened_date, low_stock_threshold, purchased_date, receipt_id, added_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.id),
                        item.item_name,
                        item.category,
                        item.quantity,
                        item.unit,
                        item.location.value,
                        item.expiration_date.isoformat() if item.expiration_date else None,
                        item.opened_date.isoformat() if item.opened_date else None,
                        item.low_stock_threshold,
                        item.purchased_date.isoformat(),
                        str(item.receipt_id) if item.receipt_id else None,
                        item.added_by,
                    ),
                )

    # --- Waste Log Operations ---

    def load_waste_log(self) -> list[WasteRecord]:
        """Load waste log records.

        Returns:
            List of WasteRecord
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM waste_log ORDER BY waste_logged_date DESC"
            ).fetchall()

            return [
                WasteRecord(
                    id=UUID(row["id"]),
                    item_name=row["item_name"],
                    quantity=row["quantity"],
                    unit=row["unit"],
                    original_purchase_date=date.fromisoformat(row["original_purchase_date"])
                    if row["original_purchase_date"]
                    else None,
                    waste_logged_date=date.fromisoformat(row["waste_logged_date"]),
                    reason=WasteReason(row["reason"]),
                    estimated_cost=row["estimated_cost"],
                    logged_by=row["logged_by"],
                )
                for row in rows
            ]

    def save_waste_log(self, records: list[WasteRecord]) -> None:
        """Save waste log records.

        Args:
            records: List of WasteRecord to save
        """
        with self._get_connection() as conn:
            # Clear existing records
            conn.execute("DELETE FROM waste_log")

            # Insert all records
            for record in records:
                conn.execute(
                    """
                    INSERT INTO waste_log
                    (id, item_name, quantity, unit, original_purchase_date,
                     waste_logged_date, reason, estimated_cost, logged_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(record.id),
                        record.item_name,
                        record.quantity,
                        record.unit,
                        record.original_purchase_date.isoformat()
                        if record.original_purchase_date
                        else None,
                        record.waste_logged_date.isoformat(),
                        record.reason.value,
                        record.estimated_cost,
                        record.logged_by,
                    ),
                )

    def add_waste_record(self, record: WasteRecord) -> UUID:
        """Add a waste record.

        Args:
            record: WasteRecord to add

        Returns:
            Record ID
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO waste_log
                (id, item_name, quantity, unit, original_purchase_date,
                 waste_logged_date, reason, estimated_cost, logged_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.id),
                    record.item_name,
                    record.quantity,
                    record.unit,
                    record.original_purchase_date.isoformat()
                    if record.original_purchase_date
                    else None,
                    record.waste_logged_date.isoformat(),
                    record.reason.value,
                    record.estimated_cost,
                    record.logged_by,
                ),
            )

        return record.id

    # --- Budget Operations ---

    def load_budget(self, month: str | None = None) -> BudgetTracking | None:
        """Load budget tracking for a month.

        Args:
            month: Month in YYYY-MM format. Defaults to current month.

        Returns:
            BudgetTracking or None
        """
        if month is None:
            month = date.today().strftime("%Y-%m")

        with self._get_connection() as conn:
            budget_row = conn.execute(
                "SELECT * FROM budgets WHERE month = ?",
                (month,),
            ).fetchone()

            if not budget_row:
                return None

            # Load category budgets
            cat_rows = conn.execute(
                "SELECT * FROM category_budgets WHERE month = ?",
                (month,),
            ).fetchall()

            category_budgets = [
                CategoryBudget(
                    category=row["category"],
                    limit=row["limit_amount"],
                    spent=row["spent"],
                )
                for row in cat_rows
            ]

            return BudgetTracking(
                month=month,
                monthly_limit=budget_row["monthly_limit"],
                category_budgets=category_budgets,
                total_spent=budget_row["total_spent"],
            )

    def save_budget(self, budget: BudgetTracking) -> None:
        """Save budget tracking.

        Args:
            budget: BudgetTracking to save
        """
        with self._get_connection() as conn:
            # Upsert budget
            conn.execute(
                """
                INSERT OR REPLACE INTO budgets
                (month, monthly_limit, total_spent)
                VALUES (?, ?, ?)
                """,
                (budget.month, budget.monthly_limit, budget.total_spent),
            )

            # Delete existing category budgets for this month
            conn.execute(
                "DELETE FROM category_budgets WHERE month = ?",
                (budget.month,),
            )

            # Insert category budgets
            for cat_budget in budget.category_budgets:
                conn.execute(
                    """
                    INSERT INTO category_budgets
                    (month, category, limit_amount, spent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (budget.month, cat_budget.category, cat_budget.limit, cat_budget.spent),
                )

    # --- User Preferences Operations ---

    def load_preferences(self) -> dict[str, UserPreferences]:
        """Load all user preferences.

        Returns:
            Dict mapping username -> UserPreferences
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM user_preferences").fetchall()

            return {
                row["user_name"]: UserPreferences(
                    user=row["user_name"],
                    brand_preferences=json.loads(row["brand_preferences"]),
                    dietary_restrictions=json.loads(row["dietary_restrictions"]),
                    allergens=json.loads(row["allergens"]),
                    favorite_items=json.loads(row["favorite_items"]),
                    shopping_patterns=json.loads(row["shopping_patterns"]),
                )
                for row in rows
            }

    def save_preferences(self, preferences: dict[str, UserPreferences]) -> None:
        """Save user preferences.

        Args:
            preferences: Dict mapping username -> UserPreferences
        """
        with self._get_connection() as conn:
            # Clear existing preferences
            conn.execute("DELETE FROM user_preferences")

            # Insert all preferences
            for user_name, prefs in preferences.items():
                conn.execute(
                    """
                    INSERT INTO user_preferences
                    (user_name, brand_preferences, dietary_restrictions,
                     allergens, favorite_items, shopping_patterns)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_name,
                        json.dumps(prefs.brand_preferences),
                        json.dumps(prefs.dietary_restrictions),
                        json.dumps(prefs.allergens),
                        json.dumps(prefs.favorite_items),
                        json.dumps(prefs.shopping_patterns),
                    ),
                )

    def get_user_preferences(self, user: str) -> UserPreferences | None:
        """Get preferences for a specific user.

        Args:
            user: Username

        Returns:
            UserPreferences or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM user_preferences WHERE user_name = ?",
                (user,),
            ).fetchone()

            if not row:
                return None

            return UserPreferences(
                user=row["user_name"],
                brand_preferences=json.loads(row["brand_preferences"]),
                dietary_restrictions=json.loads(row["dietary_restrictions"]),
                allergens=json.loads(row["allergens"]),
                favorite_items=json.loads(row["favorite_items"]),
                shopping_patterns=json.loads(row["shopping_patterns"]),
            )

    def save_user_preferences(self, prefs: UserPreferences) -> None:
        """Save preferences for a user.

        Args:
            prefs: UserPreferences to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_preferences
                (user_name, brand_preferences, dietary_restrictions,
                 allergens, favorite_items, shopping_patterns)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    prefs.user,
                    json.dumps(prefs.brand_preferences),
                    json.dumps(prefs.dietary_restrictions),
                    json.dumps(prefs.allergens),
                    json.dumps(prefs.favorite_items),
                    json.dumps(prefs.shopping_patterns),
                ),
            )
