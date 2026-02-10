"""Tests for receipt processing and reconciliation."""

from datetime import date

import pytest

from grocery_tracker.models import ItemStatus, LineItem
from grocery_tracker.receipt_processor import ReceiptInput, ReceiptProcessor


@pytest.fixture
def receipt_processor(list_manager, data_store):
    """Create a ReceiptProcessor."""
    return ReceiptProcessor(list_manager=list_manager, data_store=data_store)


class TestReceiptInput:
    """Tests for ReceiptInput validation."""

    def test_valid_receipt_input(self):
        """Create valid receipt input."""
        receipt = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99)],
            subtotal=4.99,
            total=5.29,
        )
        assert receipt.store_name == "Giant"
        assert len(receipt.line_items) == 1

    def test_empty_line_items_raises(self):
        """Empty line items raises validation error."""
        with pytest.raises(ValueError, match="at least one line item"):
            ReceiptInput(
                store_name="Giant",
                transaction_date=date(2024, 1, 15),
                line_items=[],
                subtotal=0,
                total=0,
            )


class TestItemMatching:
    """Tests for item matching logic."""

    def test_exact_match(self, receipt_processor):
        """Exact name match."""
        assert receipt_processor._items_match("Milk", "Milk") is True

    def test_case_insensitive_match(self, receipt_processor):
        """Case insensitive matching."""
        assert receipt_processor._items_match("Milk", "milk") is True
        assert receipt_processor._items_match("MILK", "milk") is True

    def test_substring_match(self, receipt_processor):
        """List item name is substring of receipt item."""
        assert receipt_processor._items_match("Bananas", "Organic Bananas") is True
        assert receipt_processor._items_match("Milk", "Whole Milk 2%") is True

    def test_canonical_suffix_match(self, receipt_processor):
        """Common packaging/percentage suffixes do not block matching."""
        assert receipt_processor._items_match("Bananas", "Organic Bananas 16oz") is True

    def test_reverse_substring_match(self, receipt_processor):
        """Receipt item name is substring of list item."""
        assert receipt_processor._items_match("Organic Bananas", "Bananas") is True

    def test_word_subset_match(self, receipt_processor):
        """All words from list item are in receipt item."""
        assert receipt_processor._items_match("Greek Yogurt", "Greek Yogurt Plain") is True

    def test_word_subset_scattered(self, receipt_processor):
        """All words from list item appear in receipt but not as contiguous substring."""
        # "rice brown" is not a substring of "brown jasmine rice"
        # but all words {"rice", "brown"} are in {"brown", "jasmine", "rice"}
        assert receipt_processor._items_match("rice brown", "brown jasmine rice") is True

    def test_primary_word_partial_match(self, receipt_processor):
        """Primary word (4+ chars) partially matches a receipt word."""
        # "pineapples" is not a substring of "pineapple juice"
        # but receipt word "pineapple" is IN list word "pineapples"
        assert receipt_processor._items_match("pineapples", "pineapple juice") is True

    def test_primary_word_too_short(self, receipt_processor):
        """Primary word under 4 chars doesn't trigger partial match."""
        # "tea" is 3 chars, not substring of "green matcha"
        assert receipt_processor._items_match("tea", "green matcha") is False

    def test_no_match(self, receipt_processor):
        """Non-matching items."""
        assert receipt_processor._items_match("Milk", "Bread") is False
        assert receipt_processor._items_match("Apple", "Orange") is False


class TestProcessReceipt:
    """Tests for receipt processing."""

    def test_process_receipt_no_list_items(self, receipt_processor):
        """Process receipt with empty shopping list."""
        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )

        result = receipt_processor.process_receipt(receipt_input)
        assert result.matched_items == 0
        assert result.newly_bought == ["Milk"]
        assert result.total_spent == 5.29

    def test_process_receipt_matches_list_items(self, list_manager, receipt_processor):
        """Process receipt that matches shopping list items."""
        # Add items to shopping list
        list_manager.add_item(name="Milk")
        list_manager.add_item(name="Bread")

        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Whole Milk", quantity=1, unit_price=4.99, total_price=4.99),
                LineItem(item_name="Wheat Bread", quantity=1, unit_price=3.49, total_price=3.49),
            ],
            subtotal=8.48,
            total=9.00,
        )

        result = receipt_processor.process_receipt(receipt_input)
        assert result.matched_items == 2
        assert result.still_needed == []
        assert result.newly_bought == []

    def test_process_receipt_partial_match(self, list_manager, receipt_processor):
        """Process receipt that partially matches shopping list."""
        # Add items to shopping list
        list_manager.add_item(name="Milk")
        list_manager.add_item(name="Bread")
        list_manager.add_item(name="Eggs")

        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
                LineItem(item_name="Cheese", quantity=1, unit_price=5.99, total_price=5.99),
            ],
            subtotal=10.98,
            total=11.63,
        )

        result = receipt_processor.process_receipt(receipt_input)
        assert result.matched_items == 1
        assert "Bread" in result.still_needed
        assert "Eggs" in result.still_needed
        assert "Cheese" in result.newly_bought

    def test_process_receipt_updates_item_status(self, list_manager, receipt_processor):
        """Processing receipt marks matched items as bought."""
        result = list_manager.add_item(name="Milk")
        item_id = result["data"]["item"]["id"]

        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )

        receipt_processor.process_receipt(receipt_input)

        # Check item is now marked as bought
        item = list_manager.get_item(item_id)
        assert item.status == ItemStatus.BOUGHT

    def test_process_receipt_updates_price_history(self, data_store, receipt_processor):
        """Processing receipt updates price history."""
        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(
                    item_name="Milk",
                    quantity=1,
                    unit_price=4.99,
                    total_price=4.99,
                    sale=True,
                ),
            ],
            subtotal=4.99,
            total=5.29,
        )

        receipt_processor.process_receipt(receipt_input)

        history = data_store.get_price_history("Milk", "Giant")
        assert history is not None
        assert len(history.price_points) == 1
        assert history.price_points[0].price == 4.99
        assert history.price_points[0].sale is True

    def test_process_receipt_persists_savings_records(self, data_store, receipt_processor):
        """Line and receipt-level discounts are persisted as savings records."""
        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(
                    item_name="Milk",
                    quantity=1,
                    unit_price=4.99,
                    total_price=4.99,
                    discount_amount=1.0,
                ),
                LineItem(
                    item_name="Bread",
                    quantity=1,
                    unit_price=3.0,
                    total_price=3.0,
                ),
            ],
            subtotal=7.99,
            discount_total=1.0,
            coupon_total=0.5,
            total=7.99,
        )

        receipt_processor.process_receipt(receipt_input)
        records = data_store.load_savings_records()

        assert len(records) == 3
        assert round(sum(record.savings_amount for record in records), 2) == 2.5
        assert any(record.source == "line_item_discount" for record in records)
        assert any(record.source == "receipt_discount" for record in records)


class TestProcessReceiptDict:
    """Tests for processing receipt from dictionary."""

    def test_process_from_dict(self, receipt_processor):
        """Process receipt from dictionary input."""
        receipt_dict = {
            "store_name": "Giant",
            "transaction_date": date(2024, 1, 15),
            "line_items": [
                {"item_name": "Milk", "quantity": 1, "unit_price": 4.99, "total_price": 4.99}
            ],
            "subtotal": 4.99,
            "total": 5.29,
        }

        result = receipt_processor.process_receipt_dict(receipt_dict)
        assert result.items_purchased == 1
        assert result.total_spent == 5.29

    def test_process_from_dict_with_discount_aliases(self, receipt_processor, data_store):
        """Dictionary processing accepts receipt-level discount aliases."""
        receipt_dict = {
            "store_name": "Giant",
            "transaction_date": date(2024, 1, 15),
            "line_items": [
                {
                    "item_name": "Milk",
                    "quantity": 1,
                    "unit_price": 4.99,
                    "total_price": 4.99,
                }
            ],
            "subtotal": 4.99,
            "receipt_discount_total": 0.5,
            "receipt_coupon_total": 0.5,
            "total": 4.99,
        }

        receipt_processor.process_receipt_dict(receipt_dict)
        records = data_store.load_savings_records()
        assert len(records) == 1
        assert records[0].savings_amount == 1.0


class TestReconciliationSummary:
    """Tests for reconciliation summary generation."""

    def test_summary_basic(self, receipt_processor, list_manager):
        """Generate basic reconciliation summary."""
        list_manager.add_item(name="Milk")

        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )

        result = receipt_processor.process_receipt(receipt_input)
        summary = receipt_processor.get_reconciliation_summary(result)

        assert "Receipt processed successfully" in summary
        assert "Items purchased: 1" in summary
        assert "$5.29" in summary

    def test_summary_with_still_needed(self, receipt_processor, list_manager):
        """Summary shows items still needed."""
        list_manager.add_item(name="Milk")
        list_manager.add_item(name="Bread")

        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )

        result = receipt_processor.process_receipt(receipt_input)
        summary = receipt_processor.get_reconciliation_summary(result)

        assert "Still needed" in summary
        assert "Bread" in summary

    def test_summary_with_new_items(self, receipt_processor):
        """Summary shows items not on list."""
        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Candy", quantity=1, unit_price=1.99, total_price=1.99),
            ],
            subtotal=1.99,
            total=2.11,
        )

        result = receipt_processor.process_receipt(receipt_input)
        summary = receipt_processor.get_reconciliation_summary(result)

        assert "New items not on list" in summary
        assert "Candy" in summary


class TestReceiptStorage:
    """Tests for receipt storage."""

    def test_receipt_saved(self, data_store, receipt_processor):
        """Processed receipt is saved to storage."""
        receipt_input = ReceiptInput(
            store_name="Giant",
            transaction_date=date(2024, 1, 15),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=4.99, total_price=4.99),
            ],
            subtotal=4.99,
            total=5.29,
        )

        result = receipt_processor.process_receipt(receipt_input)

        # Verify receipt was saved
        receipt = data_store.load_receipt(result.receipt_id)
        assert receipt is not None
        assert receipt.store_name == "Giant"
