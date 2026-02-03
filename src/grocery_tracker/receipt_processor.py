"""Receipt processing and list reconciliation."""

from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, field_validator

from .data_store import DataStore
from .list_manager import ListManager
from .models import ItemStatus, LineItem, Receipt, ReconciliationResult


class ReceiptInput(BaseModel):
    """Input model for receipt processing from external source (e.g., LLM)."""

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

    @field_validator("line_items")
    @classmethod
    def validate_line_items(cls, v: list[LineItem]) -> list[LineItem]:
        if not v:
            raise ValueError("Receipt must have at least one line item")
        return v


class ReceiptProcessor:
    """Processes receipts and reconciles with shopping list."""

    def __init__(
        self,
        list_manager: ListManager | None = None,
        data_store: DataStore | None = None,
    ):
        """Initialize receipt processor.

        Args:
            list_manager: ListManager instance
            data_store: DataStore instance
        """
        self.data_store = data_store or DataStore()
        self.list_manager = list_manager or ListManager(self.data_store)

    def process_receipt(self, receipt_input: ReceiptInput) -> ReconciliationResult:
        """Process a receipt and reconcile with shopping list.

        Args:
            receipt_input: Structured receipt data from external source

        Returns:
            ReconciliationResult with matching details
        """
        # Create and save receipt
        receipt = Receipt(
            store_name=receipt_input.store_name,
            store_location=receipt_input.store_location,
            transaction_date=receipt_input.transaction_date,
            transaction_time=receipt_input.transaction_time,
            purchased_by=receipt_input.purchased_by,
            line_items=receipt_input.line_items,
            subtotal=receipt_input.subtotal,
            tax=receipt_input.tax,
            total=receipt_input.total,
            payment_method=receipt_input.payment_method,
        )

        receipt_id = self.data_store.save_receipt(receipt)

        # Get current shopping list
        list_data = self.list_manager.get_list(status=ItemStatus.TO_BUY)
        list_items = list_data["data"]["list"]["items"]

        # Match items
        matched_items: list[str] = []
        still_needed: list[str] = []
        newly_bought: list[str] = []

        # Track which list items were matched
        matched_list_ids: set[str] = set()

        for receipt_item in receipt_input.line_items:
            matched = False
            for list_item in list_items:
                if str(list_item["id"]) in matched_list_ids:
                    continue

                if self._items_match(list_item["name"], receipt_item.item_name):
                    # Mark as matched
                    matched_list_ids.add(str(list_item["id"]))
                    matched_items.append(list_item["name"])
                    matched = True

                    # Mark item as bought in the list
                    self.list_manager.mark_bought(
                        UUID(str(list_item["id"])),
                        quantity=receipt_item.quantity,
                        price=receipt_item.total_price,
                    )

                    if receipt_item.category is None and list_item.get("category"):
                        receipt_item.category = list_item["category"]

                    # Update matched_list_item_id in receipt
                    receipt_item.matched_list_item_id = UUID(str(list_item["id"]))
                    break

            if not matched:
                newly_bought.append(receipt_item.item_name)

            # Update price history
            self._update_price_history(
                receipt_item.item_name,
                receipt_input.store_name,
                receipt_item.unit_price,
                receipt_input.transaction_date,
                receipt_id,
            )

        # Find items still needed (on list but not in receipt)
        for list_item in list_items:
            if str(list_item["id"]) not in matched_list_ids:
                still_needed.append(list_item["name"])

        # Update receipt with matched IDs
        self.data_store.save_receipt(receipt)

        # Update frequency data for all purchased items
        for receipt_item in receipt_input.line_items:
            category = receipt_item.category or "Other"
            self.data_store.update_frequency(
                item_name=receipt_item.item_name,
                purchase_date=receipt_input.transaction_date,
                quantity=receipt_item.quantity,
                store=receipt_input.store_name,
                category=category,
            )

        return ReconciliationResult(
            receipt_id=receipt_id,
            matched_items=len(matched_items),
            still_needed=still_needed,
            newly_bought=newly_bought,
            total_spent=receipt_input.total,
            items_purchased=len(receipt_input.line_items),
        )

    def process_receipt_dict(self, receipt_dict: dict) -> ReconciliationResult:
        """Process a receipt from dictionary input.

        Args:
            receipt_dict: Dictionary with receipt data

        Returns:
            ReconciliationResult with matching details
        """
        # Parse line items
        line_items = []
        for item in receipt_dict.get("line_items", []):
            line_items.append(LineItem(**item))

        receipt_input = ReceiptInput(
            store_name=receipt_dict["store_name"],
            store_location=receipt_dict.get("store_location"),
            transaction_date=receipt_dict["transaction_date"],
            transaction_time=receipt_dict.get("transaction_time"),
            purchased_by=receipt_dict.get("purchased_by"),
            line_items=line_items,
            subtotal=receipt_dict["subtotal"],
            tax=receipt_dict.get("tax", 0.0),
            total=receipt_dict["total"],
            payment_method=receipt_dict.get("payment_method"),
        )

        return self.process_receipt(receipt_input)

    def _items_match(self, list_name: str, receipt_name: str) -> bool:
        """Check if an item from the list matches one from the receipt.

        Uses fuzzy matching to account for naming differences.

        Args:
            list_name: Name from shopping list
            receipt_name: Name from receipt

        Returns:
            True if items match
        """
        list_normalized = list_name.lower().strip()
        receipt_normalized = receipt_name.lower().strip()

        # Exact match
        if list_normalized == receipt_normalized:
            return True

        # Substring match (list item in receipt or vice versa)
        if list_normalized in receipt_normalized or receipt_normalized in list_normalized:
            return True

        # Word-based matching - all words from list item in receipt
        list_words = set(list_normalized.split())
        receipt_words = set(receipt_normalized.split())

        if len(list_words) >= 2 and list_words.issubset(receipt_words):
            return True

        # Primary word match (first word matches)
        if list_words and receipt_words:
            list_primary = list(list_words)[0]
            if len(list_primary) >= 4 and any(
                list_primary in word or word in list_primary for word in receipt_words
            ):
                return True

        return False

    def _update_price_history(
        self,
        item_name: str,
        store: str,
        price: float,
        purchase_date: date,
        receipt_id: UUID,
    ) -> None:
        """Update price history for an item.

        Args:
            item_name: Name of the item
            store: Store name
            price: Unit price
            purchase_date: Date of purchase
            receipt_id: Associated receipt ID
        """
        self.data_store.update_price(
            item_name=item_name,
            store=store,
            price=price,
            purchase_date=purchase_date,
            receipt_id=receipt_id,
        )

    def get_reconciliation_summary(self, result: ReconciliationResult) -> str:
        """Generate a human-readable summary of reconciliation.

        Args:
            result: ReconciliationResult from processing

        Returns:
            Formatted summary string
        """
        lines = [
            "Receipt processed successfully!",
            "",
            f"Items purchased: {result.items_purchased}",
            f"Total spent: ${result.total_spent:.2f}",
            "",
            f"Matched from list: {result.matched_items}",
        ]

        if result.still_needed:
            lines.append("")
            lines.append(f"Still needed ({len(result.still_needed)}):")
            for item in result.still_needed:
                lines.append(f"  - {item}")

        if result.newly_bought:
            lines.append("")
            lines.append(f"New items not on list ({len(result.newly_bought)}):")
            for item in result.newly_bought:
                lines.append(f"  - {item}")

        return "\n".join(lines)
