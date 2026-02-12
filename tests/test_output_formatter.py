"""Tests for output formatting."""

import json
import re
from datetime import date, datetime, time
from io import StringIO
from uuid import uuid4

import pytest
from rich.console import Console

from grocery_tracker.output_formatter import JSONEncoder, OutputFormatter


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestJSONEncoder:
    """Tests for JSONEncoder."""

    def test_encode_uuid(self):
        """UUID encoded as string."""
        test_id = uuid4()
        result = json.dumps({"id": test_id}, cls=JSONEncoder)
        assert str(test_id) in result

    def test_encode_datetime(self):
        """Datetime encoded as ISO format."""
        dt = datetime(2024, 1, 15, 10, 30)
        result = json.dumps({"time": dt}, cls=JSONEncoder)
        assert "2024-01-15T10:30:00" in result

    def test_encode_date(self):
        """Date encoded as ISO format."""
        d = date(2024, 1, 15)
        result = json.dumps({"date": d}, cls=JSONEncoder)
        assert "2024-01-15" in result

    def test_encode_time(self):
        """Time encoded as ISO format."""
        t = time(14, 30)
        result = json.dumps({"time": t}, cls=JSONEncoder)
        assert "14:30" in result

    def test_encode_fallback(self):
        """Non-special types raise TypeError."""
        with pytest.raises(TypeError):
            json.dumps({"bad": object()}, cls=JSONEncoder)


class TestOutputFormatterJSON:
    """Tests for JSON output mode."""

    def test_json_mode_output(self, capsys):
        """JSON mode outputs valid JSON."""
        formatter = OutputFormatter(json_mode=True)
        formatter.output({"success": True, "data": {"test": "value"}})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["data"]["test"] == "value"

    def test_json_error(self, capsys):
        """JSON error output."""
        formatter = OutputFormatter(json_mode=True)
        formatter.error("Something went wrong", error_code="TEST_ERROR")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is False
        assert data["error"] == "Something went wrong"
        assert data["error_code"] == "TEST_ERROR"

    def test_json_success(self, capsys):
        """JSON success output."""
        formatter = OutputFormatter(json_mode=True)
        formatter.success("Operation completed", data={"count": 5})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["message"] == "Operation completed"
        assert data["data"]["count"] == 5

    def test_json_warning(self, capsys):
        """JSON warning output."""
        formatter = OutputFormatter(json_mode=True)
        formatter.warning("This is a warning")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["warning"] == "This is a warning"


class TestOutputFormatterRich:
    """Tests for Rich output mode."""

    def test_rich_mode_initialized(self):
        """Rich mode initializes console."""
        formatter = OutputFormatter(json_mode=False)
        assert formatter.console is not None

    def test_rich_error_output(self):
        """Rich error includes error message."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.error("Test error message")
        output = console.file.getvalue()
        assert "Test error message" in output

    def test_rich_success_output(self):
        """Rich success includes message."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.success("Test success message")
        output = console.file.getvalue()
        assert "Test success message" in output

    def test_rich_warning_output(self):
        """Rich warning includes message."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.warning("Test warning message")
        output = console.file.getvalue()
        assert "Test warning message" in output

    def test_render_empty_list(self):
        """Renders empty grocery list."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "list": {
                        "version": "1.0",
                        "last_updated": datetime.now().isoformat(),
                        "items": [],
                        "total_items": 0,
                    }
                },
            }
        )
        output = console.file.getvalue()
        assert "No items" in output

    def test_render_grocery_list(self):
        """Renders grocery list with items."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "list": {
                        "version": "1.0",
                        "last_updated": datetime.now().isoformat(),
                        "items": [
                            {
                                "name": "Milk",
                                "quantity": 2,
                                "store": "Giant",
                                "category": "Dairy",
                                "status": "to_buy",
                            },
                            {
                                "name": "Bread",
                                "quantity": 1,
                                "store": None,
                                "category": "Bakery",
                                "status": "bought",
                            },
                        ],
                        "total_items": 2,
                    }
                },
            }
        )
        output = strip_ansi(console.file.getvalue())
        assert "Milk" in output
        assert "Bread" in output
        assert "Total items: 2" in output

    def test_render_item_details(self):
        """Renders single item details."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "item": {
                        "name": "Organic Milk",
                        "quantity": 2,
                        "unit": "gallon",
                        "store": "Giant",
                        "category": "Dairy",
                        "priority": "high",
                        "status": "to_buy",
                        "brand_preference": "Horizon",
                        "estimated_price": 5.99,
                        "notes": "Whole milk only",
                    }
                },
            }
        )
        output = console.file.getvalue()
        assert "Organic Milk" in output
        assert "Giant" in output
        assert "Horizon" in output
        assert "5.99" in output
        assert "Whole milk" in output

    def test_render_by_store(self):
        """Renders items grouped by store."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "by_store": {
                        "Giant": [{"name": "Milk", "quantity": 1}],
                        "Safeway": [{"name": "Bread", "quantity": 2}],
                    }
                },
            }
        )
        output = console.file.getvalue()
        assert "Giant" in output
        assert "Safeway" in output
        assert "Milk" in output
        assert "Bread" in output

    def test_render_by_category(self):
        """Renders items grouped by category."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "by_category": {
                        "Dairy": [{"name": "Milk", "quantity": 1}],
                        "Bakery": [{"name": "Bread", "quantity": 2}],
                    }
                },
            }
        )
        output = console.file.getvalue()
        assert "Dairy" in output
        assert "Bakery" in output
        assert "Milk" in output
        assert "Bread" in output

    def test_render_reconciliation(self):
        """Renders reconciliation results."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "reconciliation": {
                        "items_purchased": 5,
                        "total_spent": 25.99,
                        "matched_items": 3,
                        "still_needed": ["Eggs", "Butter"],
                        "newly_bought": ["Candy"],
                    }
                },
            }
        )
        output = strip_ansi(console.file.getvalue())
        assert "Items purchased: 5" in output
        assert "25.99" in output
        assert "Eggs" in output
        assert "Butter" in output
        assert "Candy" in output

    def test_render_receipt(self):
        """Renders receipt details."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "receipt": {
                        "store_name": "Giant Food",
                        "transaction_date": "2024-01-15",
                        "transaction_time": "",
                        "line_items": [
                            {"item_name": "Milk", "quantity": 2, "total_price": 9.98},
                        ],
                        "total": 10.58,
                    }
                },
            }
        )
        output = console.file.getvalue()
        assert "Giant Food" in output
        assert "Milk" in output
        assert "10.58" in output

    def test_render_receipt_inferred_savings(self):
        """Renders inferred line-item savings from regular vs paid unit price."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "receipt": {
                        "store_name": "Giant Food",
                        "transaction_date": "2024-01-15",
                        "transaction_time": "",
                        "line_items": [
                            {
                                "item_name": "Milk",
                                "quantity": 2,
                                "unit_price": 4.99,
                                "regular_unit_price": 5.99,
                                "total_price": 9.98,
                            },
                        ],
                        "total": 9.98,
                    }
                },
            }
        )
        output = strip_ansi(console.file.getvalue())
        assert "Milk" in output
        assert "$2.00" in output

    def test_render_price_history(self):
        """Renders price history."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "item": "Milk",
                    "store": "Giant",
                    "current_price": 5.49,
                    "average_price": 5.25,
                    "lowest_price": 4.99,
                    "highest_price": 5.99,
                    "price_points": [
                        {"date": "2026-01-10", "price": 4.99, "sale": True},
                        {"date": "2026-01-15", "price": 5.49, "sale": False},
                        {"date": "2026-01-20", "price": 5.99, "sale": False},
                    ],
                },
            }
        )
        output = console.file.getvalue()
        assert "Milk" in output
        assert "Giant" in output
        assert "5.49" in output
        assert "5.25" in output
        assert "4.99" in output
        assert "5.99" in output
        assert "sale" in output.lower()

    def test_render_price_history_empty(self):
        """Renders price history with no price points."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {
                "success": True,
                "data": {
                    "item": "Eggs",
                    "store": "all",
                    "current_price": None,
                    "average_price": None,
                    "lowest_price": None,
                    "highest_price": None,
                    "price_points": [],
                },
            }
        )
        output = console.file.getvalue()
        assert "Eggs" in output

    def test_output_with_message_rich(self):
        """Rich output with message shows checkmark."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        formatter = OutputFormatter(json_mode=False)
        formatter.console = console

        formatter.output(
            {"success": True, "data": {"item": {"name": "Milk"}}},
            message="Added Milk to grocery list",
        )
        output = console.file.getvalue()
        assert "Added Milk" in output

    def test_json_error_without_code(self, capsys):
        """JSON error without error code."""
        formatter = OutputFormatter(json_mode=True)
        formatter.error("Something failed")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is False
        assert "error_code" not in data

    def test_json_success_without_data(self, capsys):
        """JSON success without extra data."""
        formatter = OutputFormatter(json_mode=True)
        formatter.success("Done")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert "data" not in data
