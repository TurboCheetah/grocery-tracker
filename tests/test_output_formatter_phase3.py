"""Tests for Phase 3 output formatter rendering methods."""

from io import StringIO

from rich.console import Console

from grocery_tracker.output_formatter import OutputFormatter


class TestRenderInventory:
    """Tests for inventory rendering."""

    def test_render_empty(self):
        """Renders empty inventory."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {"data": {"inventory": [], "count": 0}}
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "No items" in output

    def test_render_items(self):
        """Renders inventory items."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "inventory": [
                    {
                        "item_name": "Milk",
                        "quantity": 1,
                        "location": "fridge",
                        "category": "Dairy & Eggs",
                        "expiration_date": "2026-01-30",
                    },
                    {
                        "item_name": "Rice",
                        "quantity": 2,
                        "location": "pantry",
                        "category": "Pantry & Canned Goods",
                    },
                ],
                "count": 2,
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Inventory" in output
        assert "Milk" in output
        assert "Rice" in output


class TestRenderExpiring:
    """Tests for expiring items rendering."""

    def test_render_empty(self):
        """Renders empty expiring list."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {"data": {"expiring": [], "count": 0, "days": 3}}
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "No items expiring" in output

    def test_render_items(self):
        """Renders expiring items."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "expiring": [
                    {
                        "item_name": "Milk",
                        "expiration_date": "2026-01-28",
                        "location": "fridge",
                        "quantity": 1,
                    },
                ],
                "count": 1,
                "days": 3,
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Expiring" in output
        assert "Milk" in output


class TestRenderLowStock:
    """Tests for low stock rendering."""

    def test_render_empty(self):
        """Renders empty low stock list."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {"data": {"low_stock": [], "count": 0}}
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "No items" in output

    def test_render_items(self):
        """Renders low stock items."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "low_stock": [
                    {
                        "item_name": "Eggs",
                        "quantity": 1,
                        "low_stock_threshold": 3,
                        "location": "fridge",
                    },
                ],
                "count": 1,
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Low Stock" in output
        assert "Eggs" in output


class TestRenderWasteLog:
    """Tests for waste log rendering."""

    def test_render_empty(self):
        """Renders empty waste log."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {"data": {"waste_log": [], "count": 0}}
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "No waste" in output

    def test_render_records(self):
        """Renders waste records."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "waste_log": [
                    {
                        "item_name": "Bread",
                        "quantity": 1,
                        "reason": "spoiled",
                        "estimated_cost": 3.99,
                        "waste_logged_date": "2026-01-27",
                    },
                ],
                "count": 1,
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Waste Log" in output
        assert "Bread" in output
        assert "3.99" in output


class TestRenderWasteSummary:
    """Tests for waste summary rendering."""

    def test_render_summary(self):
        """Renders waste summary."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "waste_summary": {
                    "period": "monthly",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-27",
                    "total_items_wasted": 5,
                    "total_cost": 15.47,
                    "by_reason": {"spoiled": 3, "never_used": 2},
                    "most_wasted": [{"item": "Bread", "count": 2}],
                },
                "insights": ["Bread wasted 2 times — buy smaller quantities?"],
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Waste Summary" in output
        assert "15.47" in output
        assert "spoiled" in output
        assert "Bread" in output


class TestRenderBudgetStatus:
    """Tests for budget status rendering."""

    def test_render_status(self):
        """Renders budget status."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "budget_status": {
                    "month": "2026-01",
                    "monthly_limit": 500.0,
                    "total_spent": 350.0,
                    "category_budgets": [
                        {"category": "Produce", "limit": 100.0, "spent": 80.0},
                    ],
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Budget Status" in output
        assert "500.00" in output
        assert "350.00" in output
        assert "Produce" in output


class TestRenderPreferences:
    """Tests for preferences rendering."""

    def test_render_prefs(self):
        """Renders user preferences."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "preferences": {
                    "user": "Alice",
                    "brand_preferences": {"milk": "Organic Valley"},
                    "dietary_restrictions": ["lactose_intolerant"],
                    "allergens": ["peanuts"],
                    "favorite_items": ["mango", "dark chocolate"],
                    "shopping_patterns": {},
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Alice" in output
        assert "Organic Valley" in output
        assert "peanuts" in output
        assert "mango" in output
