"""Inventory management for Grocery Tracker."""

from datetime import date, timedelta
from uuid import UUID

from .data_store import DataStore
from .models import InventoryItem, InventoryLocation


class InventoryManager:
    """Manages household inventory tracking."""

    def __init__(self, data_store: DataStore | None = None):
        self.data_store = data_store or DataStore()

    def add_item(
        self,
        item_name: str,
        quantity: float = 1.0,
        unit: str | None = None,
        category: str = "Other",
        location: InventoryLocation = InventoryLocation.PANTRY,
        expiration_date: date | None = None,
        low_stock_threshold: float = 1.0,
        purchased_date: date | None = None,
        receipt_id: UUID | None = None,
        added_by: str | None = None,
    ) -> InventoryItem:
        """Add an item to inventory.

        Args:
            item_name: Name of the item
            quantity: Quantity in stock
            unit: Unit of measurement
            category: Product category
            location: Storage location
            expiration_date: Optional expiration date
            low_stock_threshold: Alert when quantity drops to this
            purchased_date: Date purchased
            receipt_id: Optional receipt reference
            added_by: Who added it

        Returns:
            The created InventoryItem
        """
        item = InventoryItem(
            item_name=item_name,
            quantity=quantity,
            unit=unit,
            category=category,
            location=location,
            expiration_date=expiration_date,
            low_stock_threshold=low_stock_threshold,
            purchased_date=purchased_date or date.today(),
            receipt_id=receipt_id,
            added_by=added_by,
        )

        inventory = self.data_store.load_inventory()
        inventory.append(item)
        self.data_store.save_inventory(inventory)
        return item

    def remove_item(self, item_id: str | UUID) -> InventoryItem:
        """Remove an item from inventory.

        Args:
            item_id: UUID of item to remove

        Returns:
            The removed item

        Raises:
            ValueError: If item not found
        """
        if isinstance(item_id, str):
            item_id = UUID(item_id)

        inventory = self.data_store.load_inventory()
        for i, item in enumerate(inventory):
            if item.id == item_id:
                removed = inventory.pop(i)
                self.data_store.save_inventory(inventory)
                return removed

        raise ValueError(f"Inventory item not found: {item_id}")

    def update_quantity(
        self,
        item_id: str | UUID,
        quantity: float | None = None,
        delta: float | None = None,
    ) -> InventoryItem:
        """Update item quantity.

        Args:
            item_id: UUID of item
            quantity: Set absolute quantity
            delta: Add/subtract from current quantity

        Returns:
            Updated item

        Raises:
            ValueError: If item not found or invalid args
        """
        if isinstance(item_id, str):
            item_id = UUID(item_id)

        if quantity is None and delta is None:
            raise ValueError("Must provide quantity or delta")

        inventory = self.data_store.load_inventory()
        for item in inventory:
            if item.id == item_id:
                if quantity is not None:
                    item.quantity = quantity
                elif delta is not None:
                    item.quantity = max(0, item.quantity + delta)
                self.data_store.save_inventory(inventory)
                return item

        raise ValueError(f"Inventory item not found: {item_id}")

    def update_item(
        self,
        item_id: str | UUID,
        item_name: str | None = None,
        quantity: float | None = None,
        unit: str | None = None,
        category: str | None = None,
        location: InventoryLocation | None = None,
        expiration_date: date | None = None,
        low_stock_threshold: float | None = None,
        treat_none_as_unset: bool = True,
    ) -> InventoryItem:
        """Update editable inventory fields.

        Args:
            item_id: UUID of item
            item_name: New item name
            quantity: New quantity
            unit: New unit (None clears if treat_none_as_unset is False)
            category: New category
            location: New storage location
            expiration_date: New expiration date (None clears if treat_none_as_unset is False)
            low_stock_threshold: New low-stock threshold
            treat_none_as_unset: When True, None means "leave unchanged"

        Returns:
            Updated item

        Raises:
            ValueError: If item not found
        """
        if isinstance(item_id, str):
            item_id = UUID(item_id)

        inventory = self.data_store.load_inventory()
        for item in inventory:
            if item.id == item_id:
                if item_name is not None:
                    item.item_name = item_name
                if quantity is not None:
                    item.quantity = quantity
                if unit is not None or not treat_none_as_unset:
                    item.unit = unit
                if category is not None:
                    item.category = category
                if location is not None:
                    item.location = location
                if expiration_date is not None or not treat_none_as_unset:
                    item.expiration_date = expiration_date
                if low_stock_threshold is not None:
                    item.low_stock_threshold = low_stock_threshold

                self.data_store.save_inventory(inventory)
                return item

        raise ValueError(f"Inventory item not found: {item_id}")

    def get_inventory(
        self,
        location: InventoryLocation | None = None,
        category: str | None = None,
    ) -> list[InventoryItem]:
        """Get inventory items with optional filters.

        Args:
            location: Filter by storage location
            category: Filter by category

        Returns:
            List of matching inventory items
        """
        inventory = self.data_store.load_inventory()

        if location:
            inventory = [i for i in inventory if i.location == location]
        if category:
            inventory = [i for i in inventory if i.category.lower() == category.lower()]

        return inventory

    def get_expiring_soon(self, days: int = 3) -> list[InventoryItem]:
        """Get items expiring within a number of days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of expiring items sorted by expiration date
        """
        cutoff = date.today() + timedelta(days=days)
        inventory = self.data_store.load_inventory()

        expiring = [
            i for i in inventory if i.expiration_date is not None and i.expiration_date <= cutoff
        ]

        return sorted(expiring, key=lambda i: i.expiration_date)  # type: ignore[arg-type, return-value]

    def get_low_stock(self) -> list[InventoryItem]:
        """Get items that are at or below low stock threshold.

        Returns:
            List of low-stock items
        """
        inventory = self.data_store.load_inventory()
        return [i for i in inventory if i.is_low_stock]

    def add_from_receipt(self, receipt) -> list[InventoryItem]:
        """Add items to inventory from a processed receipt.

        Args:
            receipt: A Receipt object

        Returns:
            List of created inventory items
        """
        added = []
        for line_item in receipt.line_items:
            item = self.add_item(
                item_name=line_item.item_name,
                quantity=line_item.quantity,
                purchased_date=receipt.transaction_date,
                receipt_id=receipt.id,
            )
            added.append(item)
        return added
