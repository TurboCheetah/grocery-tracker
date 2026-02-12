"""Receipt processing and list reconciliation."""

from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, field_validator

from .data_store import DataStore
from .item_normalizer import canonical_item_display_name, normalize_item_name
from .list_manager import ListManager
from .models import ItemStatus, LineItem, Receipt, ReconciliationResult, SavingsRecord


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
    discount_total: float = 0.0
    coupon_total: float = 0.0
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
            discount_total=receipt_input.discount_total,
            coupon_total=receipt_input.coupon_total,
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

                    # Update matched_list_item_id in receipt
                    receipt_item.matched_list_item_id = UUID(str(list_item["id"]))
                    break

            if not matched:
                newly_bought.append(receipt_item.item_name)

            # Update price history
            self._update_price_history(
                canonical_item_display_name(receipt_item.item_name),
                receipt_input.store_name,
                receipt_item.unit_price,
                receipt_input.transaction_date,
                receipt_id,
                sale=self._line_item_has_sale(receipt_item),
            )

        # Find items still needed (on list but not in receipt)
        for list_item in list_items:
            if str(list_item["id"]) not in matched_list_ids:
                still_needed.append(list_item["name"])

        # Update receipt with matched IDs
        self.data_store.save_receipt(receipt)

        # Update frequency data for all purchased items
        for receipt_item in receipt_input.line_items:
            self.data_store.update_frequency(
                item_name=canonical_item_display_name(receipt_item.item_name),
                purchase_date=receipt_input.transaction_date,
                quantity=receipt_item.quantity,
                store=receipt_input.store_name,
            )

        self._persist_savings_records(receipt)

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
            discount_total=receipt_dict.get(
                "discount_total",
                receipt_dict.get("receipt_discount_total", 0.0),
            ),
            coupon_total=receipt_dict.get(
                "coupon_total",
                receipt_dict.get("receipt_coupon_total", 0.0),
            ),
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
        list_normalized = normalize_item_name(list_name)
        receipt_normalized = normalize_item_name(receipt_name)

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
        sale: bool = False,
    ) -> None:
        """Update price history for an item.

        Args:
            item_name: Name of the item
            store: Store name
            price: Unit price
            purchase_date: Date of purchase
            receipt_id: Associated receipt ID
            sale: Whether this line item was on sale/discount
        """
        self.data_store.update_price(
            item_name=item_name,
            store=store,
            price=price,
            purchase_date=purchase_date,
            receipt_id=receipt_id,
            sale=sale,
        )

    def _persist_savings_records(self, receipt: Receipt) -> None:
        """Persist line-item and receipt-level savings as normalized records."""
        receipt_level_savings = max(receipt.discount_total, 0.0) + max(receipt.coupon_total, 0.0)
        allocated_receipt_savings = self._allocate_receipt_level_savings(
            receipt_level_savings,
            receipt.line_items,
        )

        for index, line_item in enumerate(receipt.line_items):
            category = self._line_item_category(line_item)
            line_item_savings = self._line_item_savings(line_item)
            receipt_allocated = allocated_receipt_savings[index]

            if line_item_savings > 0:
                self.data_store.add_savings_record(
                    SavingsRecord(
                        receipt_id=receipt.id,
                        transaction_date=receipt.transaction_date,
                        store=receipt.store_name,
                        item_name=canonical_item_display_name(line_item.item_name),
                        category=category,
                        savings_amount=line_item_savings,
                        source="line_item_discount",
                        quantity=line_item.quantity,
                        paid_unit_price=line_item.unit_price,
                        regular_unit_price=line_item.regular_unit_price,
                    )
                )

            if receipt_allocated > 0:
                self.data_store.add_savings_record(
                    SavingsRecord(
                        receipt_id=receipt.id,
                        transaction_date=receipt.transaction_date,
                        store=receipt.store_name,
                        item_name=canonical_item_display_name(line_item.item_name),
                        category=category,
                        savings_amount=receipt_allocated,
                        source="receipt_discount",
                        quantity=line_item.quantity,
                        paid_unit_price=line_item.unit_price,
                        regular_unit_price=line_item.regular_unit_price,
                    )
                )

    @staticmethod
    def _line_item_has_sale(line_item: LineItem) -> bool:
        """Determine whether a line item should be flagged as a sale price."""
        if line_item.sale:
            return True
        if line_item.discount_amount > 0 or line_item.coupon_amount > 0:
            return True
        return (
            line_item.regular_unit_price is not None
            and line_item.regular_unit_price > line_item.unit_price
        )

    @staticmethod
    def _line_item_savings(line_item: LineItem) -> float:
        """Calculate explicit/inferred savings from a line item."""
        explicit = max(line_item.discount_amount, 0.0) + max(line_item.coupon_amount, 0.0)
        if explicit > 0:
            return round(explicit, 2)

        if (
            line_item.regular_unit_price is not None
            and line_item.regular_unit_price > line_item.unit_price
        ):
            inferred = (line_item.regular_unit_price - line_item.unit_price) * line_item.quantity
            return round(max(inferred, 0.0), 2)

        return 0.0

    @staticmethod
    def _allocate_receipt_level_savings(
        total_discount: float,
        line_items: list[LineItem],
    ) -> list[float]:
        """Allocate receipt-level savings across line items using deterministic weighting."""
        if not line_items or total_discount <= 0:
            return [0.0] * len(line_items)

        total_cents = max(int(round(total_discount * 100)), 0)
        if total_cents == 0:
            return [0.0] * len(line_items)

        weights = [max(item.total_price, 0.0) for item in line_items]
        weight_sum = sum(weights)
        if weight_sum <= 0:
            weights = [1.0] * len(line_items)
            weight_sum = float(len(line_items))

        raw_cents = [total_cents * (weight / weight_sum) for weight in weights]
        allocated_cents = [int(value) for value in raw_cents]
        remainder = total_cents - sum(allocated_cents)
        if remainder > 0:
            order = sorted(
                range(len(line_items)),
                key=lambda idx: (
                    raw_cents[idx] - allocated_cents[idx],
                    weights[idx],
                    line_items[idx].item_name.lower(),
                ),
                reverse=True,
            )
            for idx in order[:remainder]:
                allocated_cents[idx] += 1

        return [round(cents / 100, 2) for cents in allocated_cents]

    def _line_item_category(self, line_item: LineItem) -> str:
        """Infer line item category from matched grocery list item when available."""
        if line_item.matched_list_item_id:
            matched_item = self.data_store.get_item(line_item.matched_list_item_id)
            if matched_item and matched_item.category:
                return matched_item.category
        return "Other"

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
