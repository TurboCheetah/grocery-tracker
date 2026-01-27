"""Grocery list management operations."""

from datetime import datetime
from uuid import UUID

from .data_store import DataStore
from .models import Category, GroceryItem, ItemStatus, Priority


class DuplicateItemError(Exception):
    """Raised when attempting to add a duplicate item."""

    def __init__(self, existing_item: GroceryItem):
        self.existing_item = existing_item
        super().__init__(
            f"Item '{existing_item.name}' already exists on the list "
            f"(quantity: {existing_item.quantity}, store: {existing_item.store})"
        )


class ItemNotFoundError(Exception):
    """Raised when an item is not found."""

    def __init__(self, item_id: UUID | str):
        self.item_id = item_id
        super().__init__(f"Item with ID '{item_id}' not found")


class ListManager:
    """Manages grocery list operations."""

    def __init__(self, data_store: DataStore | None = None):
        """Initialize list manager.

        Args:
            data_store: DataStore instance. Creates new one if not provided.
        """
        self.data_store = data_store or DataStore()

    def add_item(
        self,
        name: str,
        quantity: float | str = 1,
        store: str | None = None,
        category: str | None = None,
        unit: str | None = None,
        brand_preference: str | None = None,
        estimated_price: float | None = None,
        priority: Priority = Priority.MEDIUM,
        added_by: str | None = None,
        notes: str | None = None,
        allow_duplicate: bool = False,
    ) -> dict:
        """Add an item to the grocery list.

        Args:
            name: Item name
            quantity: Amount to buy
            store: Store to buy from
            category: Product category
            unit: Unit of measurement
            brand_preference: Preferred brand
            estimated_price: Estimated cost
            priority: Item priority
            added_by: User who added the item
            notes: Additional notes
            allow_duplicate: Whether to allow duplicate items

        Returns:
            Dict with success status and item data

        Raises:
            DuplicateItemError: If duplicate found and not allowed
        """
        grocery_list = self.data_store.load_list()

        # Check for duplicates
        if not allow_duplicate:
            for existing in grocery_list.items:
                if existing.name.lower() == name.lower() and existing.status == ItemStatus.TO_BUY:
                    raise DuplicateItemError(existing)

        # Create new item
        item = GroceryItem(
            name=name,
            quantity=quantity,
            store=store,
            category=category or Category.OTHER.value,
            unit=unit,
            brand_preference=brand_preference,
            estimated_price=estimated_price,
            priority=priority,
            added_by=added_by,
            notes=notes,
            added_at=datetime.now(),
            status=ItemStatus.TO_BUY,
        )

        grocery_list.items.append(item)
        self.data_store.save_list(grocery_list)

        return {
            "success": True,
            "message": f"Added {name} to grocery list",
            "data": {"item": item.model_dump(mode="json")},
        }

    def remove_item(self, item_id: UUID | str) -> dict:
        """Remove an item from the grocery list.

        Args:
            item_id: ID of item to remove

        Returns:
            Dict with success status

        Raises:
            ItemNotFoundError: If item not found
        """
        if isinstance(item_id, str):
            item_id = UUID(item_id)

        grocery_list = self.data_store.load_list()

        for i, item in enumerate(grocery_list.items):
            if item.id == item_id:
                removed = grocery_list.items.pop(i)
                self.data_store.save_list(grocery_list)
                return {
                    "success": True,
                    "message": f"Removed {removed.name} from grocery list",
                    "data": {"item": removed.model_dump(mode="json")},
                }

        raise ItemNotFoundError(item_id)

    def get_list(
        self,
        store: str | None = None,
        category: str | None = None,
        status: ItemStatus | None = None,
    ) -> dict:
        """Get the grocery list with optional filtering.

        Args:
            store: Filter by store
            category: Filter by category
            status: Filter by status

        Returns:
            Dict with list data
        """
        grocery_list = self.data_store.load_list()
        items = grocery_list.items

        # Apply filters
        if store:
            items = [i for i in items if i.store and i.store.lower() == store.lower()]

        if category:
            items = [i for i in items if i.category.lower() == category.lower()]

        if status:
            items = [i for i in items if i.status == status]

        return {
            "success": True,
            "data": {
                "list": {
                    "version": grocery_list.version,
                    "last_updated": grocery_list.last_updated.isoformat(),
                    "items": [item.model_dump(mode="json") for item in items],
                    "total_items": len(items),
                }
            },
        }

    def get_item(self, item_id: UUID | str) -> GroceryItem:
        """Get a specific item by ID.

        Args:
            item_id: Item ID

        Returns:
            GroceryItem

        Raises:
            ItemNotFoundError: If item not found
        """
        if isinstance(item_id, str):
            item_id = UUID(item_id)

        item = self.data_store.get_item(item_id)
        if not item:
            raise ItemNotFoundError(item_id)
        return item

    def mark_bought(
        self,
        item_id: UUID | str,
        quantity: float | None = None,
        price: float | None = None,
    ) -> dict:
        """Mark an item as bought.

        Args:
            item_id: ID of item to mark
            quantity: Actual quantity bought (optional)
            price: Actual price paid (optional)

        Returns:
            Dict with success status

        Raises:
            ItemNotFoundError: If item not found
        """
        if isinstance(item_id, str):
            item_id = UUID(item_id)

        grocery_list = self.data_store.load_list()

        for item in grocery_list.items:
            if item.id == item_id:
                item.status = ItemStatus.BOUGHT
                if quantity is not None:
                    item.quantity = quantity
                if price is not None:
                    item.estimated_price = price

                self.data_store.save_list(grocery_list)
                return {
                    "success": True,
                    "message": f"Marked {item.name} as bought",
                    "data": {"item": item.model_dump(mode="json")},
                }

        raise ItemNotFoundError(item_id)

    def update_item(
        self,
        item_id: UUID | str,
        name: str | None = None,
        quantity: float | str | None = None,
        store: str | None = None,
        category: str | None = None,
        unit: str | None = None,
        brand_preference: str | None = None,
        estimated_price: float | None = None,
        priority: Priority | None = None,
        notes: str | None = None,
        status: ItemStatus | None = None,
    ) -> dict:
        """Update an existing item.

        Args:
            item_id: ID of item to update
            **kwargs: Fields to update

        Returns:
            Dict with success status

        Raises:
            ItemNotFoundError: If item not found
        """
        if isinstance(item_id, str):
            item_id = UUID(item_id)

        grocery_list = self.data_store.load_list()

        for item in grocery_list.items:
            if item.id == item_id:
                if name is not None:
                    item.name = name
                if quantity is not None:
                    item.quantity = quantity
                if store is not None:
                    item.store = store
                if category is not None:
                    item.category = category
                if unit is not None:
                    item.unit = unit
                if brand_preference is not None:
                    item.brand_preference = brand_preference
                if estimated_price is not None:
                    item.estimated_price = estimated_price
                if priority is not None:
                    item.priority = priority
                if notes is not None:
                    item.notes = notes
                if status is not None:
                    item.status = status

                self.data_store.save_list(grocery_list)
                return {
                    "success": True,
                    "message": f"Updated {item.name}",
                    "data": {"item": item.model_dump(mode="json")},
                }

        raise ItemNotFoundError(item_id)

    def clear_bought(self) -> dict:
        """Remove all bought items from the list.

        Returns:
            Dict with count of removed items
        """
        grocery_list = self.data_store.load_list()
        original_count = len(grocery_list.items)

        grocery_list.items = [
            item for item in grocery_list.items if item.status != ItemStatus.BOUGHT
        ]

        removed_count = original_count - len(grocery_list.items)
        self.data_store.save_list(grocery_list)

        return {
            "success": True,
            "message": f"Cleared {removed_count} bought items",
            "data": {"removed_count": removed_count},
        }

    def get_by_store(self) -> dict:
        """Get items grouped by store.

        Returns:
            Dict with items grouped by store
        """
        grocery_list = self.data_store.load_list()

        by_store: dict[str, list[dict]] = {}
        for item in grocery_list.items:
            store = item.store or "Unspecified"
            if store not in by_store:
                by_store[store] = []
            by_store[store].append(item.model_dump(mode="json"))

        return {
            "success": True,
            "data": {"by_store": by_store},
        }

    def get_by_category(self) -> dict:
        """Get items grouped by category.

        Returns:
            Dict with items grouped by category
        """
        grocery_list = self.data_store.load_list()

        by_category: dict[str, list[dict]] = {}
        for item in grocery_list.items:
            cat = item.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item.model_dump(mode="json"))

        return {
            "success": True,
            "data": {"by_category": by_category},
        }
