"""Tests for CLI commands."""

import json
import re

from typer.testing import CliRunner

from grocery_tracker.main import app

runner = CliRunner()

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class TestFlexibleGlobalOptions:
    """Tests for flexible placement of selected global options."""

    def test_list_accepts_trailing_global_flags(self, temp_data_dir):
        """Allow --json/--data-dir after the subcommand."""
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])

        result = runner.invoke(app, ["list", "--json", "--data-dir", str(temp_data_dir)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["data"]["list"]["total_items"] == 1

    def test_list_accepts_data_dir_equals_form(self, temp_data_dir):
        """Allow --data-dir=<path> form after the subcommand."""
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])

        result = runner.invoke(app, ["list", f"--data-dir={temp_data_dir}", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["data"]["list"]["total_items"] == 1


class TestAddCommand:
    """Tests for add command."""

    def test_add_item_basic(self, temp_data_dir):
        """Add item with basic options."""
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["data"]["item"]["name"] == "Milk"

    def test_add_item_with_options(self, temp_data_dir):
        """Add item with all options."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "add",
                "Organic Milk",
                "--quantity",
                "2",
                "--store",
                "Giant",
                "--category",
                "Dairy",
                "--unit",
                "gallon",
                "--brand",
                "Horizon",
                "--price",
                "5.99",
                "--priority",
                "high",
                "--by",
                "Alice",
                "--notes",
                "Whole milk only",
            ],
        )
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        item = data["data"]["item"]
        assert item["name"] == "Organic Milk"
        assert item["quantity"] == 2.0
        assert item["store"] == "Giant"
        assert item["priority"] == "high"

    def test_add_duplicate_fails(self, temp_data_dir):
        """Adding duplicate item fails."""
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        assert result.exit_code == 1

        data = json.loads(result.stdout)
        assert data["success"] is False
        assert "DUPLICATE_ITEM" in data.get("error_code", "")

    def test_add_duplicate_with_force(self, temp_data_dir):
        """Adding duplicate with --force succeeds."""
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        result = runner.invoke(
            app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk", "--force"]
        )
        assert result.exit_code == 0


class TestListCommand:
    """Tests for list command."""

    def test_list_empty(self, temp_data_dir):
        """List empty grocery list."""
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "list"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["data"]["list"]["items"] == []

    def test_list_with_items(self, temp_data_dir):
        """List grocery list with items."""
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Bread"])

        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "list"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert len(data["data"]["list"]["items"]) == 2

    def test_list_filter_by_store(self, temp_data_dir):
        """Filter list by store."""
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "add",
                "Milk",
                "--store",
                "Giant",
            ],
        )
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "add",
                "Bread",
                "--store",
                "Safeway",
            ],
        )

        result = runner.invoke(
            app,
            ["--json", "--data-dir", str(temp_data_dir), "list", "--store", "Giant"],
        )
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert len(data["data"]["list"]["items"]) == 1
        assert data["data"]["list"]["items"][0]["name"] == "Milk"


class TestBoughtCommand:
    """Tests for bought command."""

    def test_mark_bought(self, temp_data_dir):
        """Mark item as bought."""
        # Add item
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]

        # Mark as bought
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "bought", item_id])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["data"]["item"]["status"] == "bought"

    def test_mark_bought_with_price(self, temp_data_dir):
        """Mark item as bought with price."""
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "bought",
                item_id,
                "--price",
                "4.99",
            ],
        )
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["data"]["item"]["estimated_price"] == 4.99


class TestRemoveCommand:
    """Tests for remove command."""

    def test_remove_item(self, temp_data_dir):
        """Remove item from list."""
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]

        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "remove", item_id])
        assert result.exit_code == 0

        # Verify item is gone
        list_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "list"])
        data = json.loads(list_result.stdout)
        assert len(data["data"]["list"]["items"]) == 0


class TestUpdateCommand:
    """Tests for update command."""

    def test_update_item(self, temp_data_dir):
        """Update item fields."""
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "update",
                item_id,
                "--name",
                "Whole Milk",
                "--quantity",
                "2",
            ],
        )
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["data"]["item"]["name"] == "Whole Milk"
        assert data["data"]["item"]["quantity"] == 2.0


class TestClearCommand:
    """Tests for clear command."""

    def test_clear_bought(self, temp_data_dir):
        """Clear bought items."""
        # Add and buy item
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "bought", item_id])

        # Add unbought item
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Bread"])

        # Clear bought
        result = runner.invoke(
            app, ["--json", "--data-dir", str(temp_data_dir), "clear", "--bought"]
        )
        assert result.exit_code == 0

        # Verify only Bread remains
        list_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "list"])
        data = json.loads(list_result.stdout)
        assert len(data["data"]["list"]["items"]) == 1
        assert data["data"]["list"]["items"][0]["name"] == "Bread"


class TestReceiptCommands:
    """Tests for receipt subcommands."""

    def test_process_receipt(self, temp_data_dir):
        """Process receipt data."""
        receipt_data = json.dumps(
            {
                "store_name": "Giant",
                "transaction_date": "2024-01-15",
                "line_items": [
                    {
                        "item_name": "Milk",
                        "quantity": 1,
                        "unit_price": 4.99,
                        "total_price": 4.99,
                    }
                ],
                "subtotal": 4.99,
                "total": 5.29,
            }
        )

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "receipt",
                "process",
                "--data",
                receipt_data,
            ],
        )
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["data"]["reconciliation"]["items_purchased"] == 1

    def test_list_receipts_empty(self, temp_data_dir):
        """List receipts when none exist."""
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "receipt", "list"])
        assert result.exit_code == 0


class TestPriceCommands:
    """Tests for price subcommands."""

    def test_price_history_not_found(self, temp_data_dir):
        """Price history for unknown item."""
        result = runner.invoke(
            app,
            ["--json", "--data-dir", str(temp_data_dir), "price", "history", "Unknown"],
        )
        # Should succeed but show warning
        assert result.exit_code == 0

    def test_price_history_with_data(self, temp_data_dir):
        """Price history after processing a receipt."""
        receipt_data = json.dumps(
            {
                "store_name": "Giant",
                "transaction_date": "2026-01-15",
                "line_items": [
                    {
                        "item_name": "Milk",
                        "quantity": 1,
                        "unit_price": 4.99,
                        "total_price": 4.99,
                    }
                ],
                "subtotal": 4.99,
                "total": 4.99,
            }
        )
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "receipt",
                "process",
                "--data",
                receipt_data,
            ],
        )

        result = runner.invoke(
            app,
            ["--json", "--data-dir", str(temp_data_dir), "price", "history", "Milk"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["data"]["current_price"] == 4.99

    def test_price_history_filter_by_store(self, temp_data_dir):
        """Price history filtered by store."""
        receipt_data = json.dumps(
            {
                "store_name": "Giant",
                "transaction_date": "2026-01-15",
                "line_items": [
                    {
                        "item_name": "Milk",
                        "quantity": 1,
                        "unit_price": 4.99,
                        "total_price": 4.99,
                    }
                ],
                "subtotal": 4.99,
                "total": 4.99,
            }
        )
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "receipt",
                "process",
                "--data",
                receipt_data,
            ],
        )

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "price",
                "history",
                "Milk",
                "--store",
                "Giant",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["store"] == "Giant"


class TestRemoveErrors:
    """Tests for remove command error handling."""

    def test_remove_nonexistent(self, temp_data_dir):
        """Remove non-existent item returns error."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "remove",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert data["error_code"] == "ITEM_NOT_FOUND"

    def test_remove_invalid_uuid(self, temp_data_dir):
        """Remove with invalid UUID returns error."""
        result = runner.invoke(
            app,
            ["--json", "--data-dir", str(temp_data_dir), "remove", "not-a-uuid"],
        )
        assert result.exit_code == 1


class TestBoughtErrors:
    """Tests for bought command error handling."""

    def test_bought_nonexistent(self, temp_data_dir):
        """Mark non-existent item as bought returns error."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "bought",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert data["error_code"] == "ITEM_NOT_FOUND"

    def test_bought_with_quantity(self, temp_data_dir):
        """Mark bought with quantity option."""
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Eggs"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "bought",
                item_id,
                "--quantity",
                "12",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["item"]["quantity"] == 12.0


class TestUpdateErrors:
    """Tests for update command error handling."""

    def test_update_nonexistent(self, temp_data_dir):
        """Update non-existent item returns error."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "update",
                "00000000-0000-0000-0000-000000000000",
                "--name",
                "New Name",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert data["error_code"] == "ITEM_NOT_FOUND"

    def test_update_all_fields(self, temp_data_dir):
        """Update all available fields."""
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "update",
                item_id,
                "--name",
                "Whole Milk",
                "--store",
                "Giant",
                "--category",
                "Dairy",
                "--unit",
                "gallon",
                "--brand",
                "Horizon",
                "--price",
                "5.99",
                "--priority",
                "high",
                "--notes",
                "Organic only",
                "--status",
                "still_needed",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        item = data["data"]["item"]
        assert item["name"] == "Whole Milk"
        assert item["store"] == "Giant"
        assert item["unit"] == "gallon"
        assert item["brand_preference"] == "Horizon"
        assert item["estimated_price"] == 5.99
        assert item["priority"] == "high"
        assert item["notes"] == "Organic only"
        assert item["status"] == "still_needed"


class TestListGrouping:
    """Tests for list grouping options."""

    def test_list_by_store(self, temp_data_dir):
        """List items grouped by store."""
        runner.invoke(
            app,
            ["--json", "--data-dir", str(temp_data_dir), "add", "Milk", "--store", "Giant"],
        )
        runner.invoke(
            app,
            ["--json", "--data-dir", str(temp_data_dir), "add", "Bread", "--store", "Safeway"],
        )

        result = runner.invoke(
            app, ["--json", "--data-dir", str(temp_data_dir), "list", "--by-store"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "by_store" in data["data"]
        assert "Giant" in data["data"]["by_store"]

    def test_list_by_category(self, temp_data_dir):
        """List items grouped by category."""
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "add",
                "Milk",
                "--category",
                "Dairy",
            ],
        )
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "add",
                "Apples",
                "--category",
                "Produce",
            ],
        )

        result = runner.invoke(
            app, ["--json", "--data-dir", str(temp_data_dir), "list", "--by-category"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "by_category" in data["data"]

    def test_list_filter_by_status(self, temp_data_dir):
        """List filtered by status."""
        add_result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        item_id = json.loads(add_result.stdout)["data"]["item"]["id"]
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "bought", item_id])
        runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Bread"])

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "list",
                "--status",
                "to_buy",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        items = data["data"]["list"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Bread"

    def test_list_filter_by_category(self, temp_data_dir):
        """List filtered by category."""
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "add",
                "Milk",
                "--category",
                "Dairy",
            ],
        )
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "add",
                "Apples",
                "--category",
                "Produce",
            ],
        )

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "list",
                "--category",
                "Dairy",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["data"]["list"]["items"]) == 1


class TestReceiptFile:
    """Tests for receipt processing from file."""

    def test_process_receipt_from_file(self, temp_data_dir, sample_receipt_data):
        """Process receipt from JSON file."""
        receipt_file = temp_data_dir / "test_receipt.json"
        receipt_file.write_text(json.dumps(sample_receipt_data))

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "receipt",
                "process",
                "--file",
                str(receipt_file),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True

    def test_process_receipt_no_input(self, temp_data_dir):
        """Process receipt without data or file fails."""
        result = runner.invoke(
            app,
            ["--json", "--data-dir", str(temp_data_dir), "receipt", "process"],
        )
        assert result.exit_code == 1

    def test_process_receipt_invalid_json(self, temp_data_dir):
        """Process receipt with invalid JSON fails."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "receipt",
                "process",
                "--data",
                "not valid json",
            ],
        )
        assert result.exit_code == 1

    def test_list_receipts_with_data(self, temp_data_dir, sample_receipt_json):
        """List receipts after processing one."""
        runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "receipt",
                "process",
                "--data",
                sample_receipt_json,
            ],
        )

        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "receipt", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert len(data["data"]["receipts"]) == 1
        assert data["data"]["receipts"][0]["store"] == "Giant Food"


class TestRichOutput:
    """Tests for Rich (non-JSON) output mode."""

    def test_add_rich_output(self, temp_data_dir):
        """Add item in rich mode."""
        result = runner.invoke(app, ["--data-dir", str(temp_data_dir), "add", "Milk"])
        assert result.exit_code == 0
        assert "Added Milk" in result.stdout

    def test_list_rich_output(self, temp_data_dir):
        """List items in rich mode."""
        runner.invoke(app, ["--data-dir", str(temp_data_dir), "add", "Milk"])
        result = runner.invoke(app, ["--data-dir", str(temp_data_dir), "list"])
        assert result.exit_code == 0
        assert "Milk" in result.stdout


class TestHelpCommand:
    """Tests for help output."""

    def test_main_help(self):
        """Main help output."""
        result = runner.invoke(app, ["--help"])
        output = ANSI_ESCAPE_RE.sub("", result.stdout)
        assert result.exit_code == 0
        assert "grocery" in output.lower()
        assert "add" in output
        assert "--json" in output
        assert "--data-dir" in output

    def test_add_help(self):
        """Add command help."""
        result = runner.invoke(app, ["add", "--help"])
        assert result.exit_code == 0
        assert "item" in result.stdout.lower()


class TestClearWithoutBought:
    """Tests for clear command without --bought."""

    def test_clear_all_fails(self, temp_data_dir):
        """Clear --all fails with guidance message."""
        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "clear", "--all"])
        assert result.exit_code == 1
        # May produce multiple JSON lines, take the first
        first_line = result.stdout.strip().split("\n")[0]
        data = json.loads(first_line)
        assert data["success"] is False


class TestGenericExceptionHandling:
    """Tests for generic exception error paths in CLI commands."""

    def test_add_unexpected_error(self, temp_data_dir, monkeypatch):
        """Add command handles unexpected errors."""
        from grocery_tracker import list_manager as lm_module

        monkeypatch.setattr(
            lm_module.ListManager,
            "add_item",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "add", "Milk"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert "boom" in data["error"]

    def test_list_unexpected_error(self, temp_data_dir, monkeypatch):
        """List command handles unexpected errors."""
        from grocery_tracker import list_manager as lm_module

        monkeypatch.setattr(
            lm_module.ListManager,
            "get_list",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("list boom")),
        )

        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "list"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "list boom" in data["error"]

    def test_bought_unexpected_error(self, temp_data_dir, monkeypatch):
        """Bought command handles unexpected errors."""
        from grocery_tracker import list_manager as lm_module

        monkeypatch.setattr(
            lm_module.ListManager,
            "mark_bought",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("bought boom")),
        )

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "bought",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "bought boom" in data["error"]

    def test_update_unexpected_error(self, temp_data_dir, monkeypatch):
        """Update command handles unexpected errors."""
        from grocery_tracker import list_manager as lm_module

        monkeypatch.setattr(
            lm_module.ListManager,
            "update_item",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("update boom")),
        )

        result = runner.invoke(
            app,
            [
                "--json",
                "--data-dir",
                str(temp_data_dir),
                "update",
                "00000000-0000-0000-0000-000000000000",
                "--name",
                "X",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "update boom" in data["error"]

    def test_receipt_list_unexpected_error(self, temp_data_dir, monkeypatch):
        """Receipt list command handles unexpected errors."""
        from grocery_tracker import data_store as ds_module

        monkeypatch.setattr(
            ds_module.DataStore,
            "list_receipts",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("receipt boom")),
        )

        result = runner.invoke(app, ["--json", "--data-dir", str(temp_data_dir), "receipt", "list"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "receipt boom" in data["error"]

    def test_price_history_unexpected_error(self, temp_data_dir, monkeypatch):
        """Price history command handles unexpected errors."""
        from grocery_tracker import data_store as ds_module

        monkeypatch.setattr(
            ds_module.DataStore,
            "get_price_history",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("price boom")),
        )

        result = runner.invoke(
            app, ["--json", "--data-dir", str(temp_data_dir), "price", "history", "Milk"]
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "price boom" in data["error"]
