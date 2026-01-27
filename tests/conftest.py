"""Shared test fixtures for Grocery Tracker."""

import json

import pytest

from grocery_tracker.data_store import DataStore
from grocery_tracker.list_manager import ListManager
from grocery_tracker.receipt_processor import ReceiptProcessor


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def data_store(temp_data_dir):
    """Create a DataStore with temporary directory."""
    return DataStore(data_dir=temp_data_dir)


@pytest.fixture
def list_manager(data_store):
    """Create a ListManager with temporary storage."""
    return ListManager(data_store=data_store)


@pytest.fixture
def receipt_processor(data_store, list_manager):
    """Create a ReceiptProcessor with temporary storage."""
    return ReceiptProcessor(list_manager=list_manager, data_store=data_store)


@pytest.fixture
def sample_receipt_data():
    """Sample receipt data dictionary for testing."""
    return {
        "store_name": "Giant Food",
        "transaction_date": "2026-01-25",
        "transaction_time": "14:32",
        "line_items": [
            {
                "item_name": "Bananas",
                "quantity": 3,
                "unit_price": 0.49,
                "total_price": 1.47,
            },
            {
                "item_name": "Milk",
                "quantity": 1,
                "unit_price": 5.49,
                "total_price": 5.49,
            },
        ],
        "subtotal": 6.96,
        "tax": 0.00,
        "total": 6.96,
    }


@pytest.fixture
def sample_receipt_json(sample_receipt_data):
    """Sample receipt data as JSON string."""
    return json.dumps(sample_receipt_data)
