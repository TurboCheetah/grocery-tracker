"""Tests for Phase 2 output formatter rendering methods."""

from io import StringIO

from rich.console import Console

from grocery_tracker.output_formatter import OutputFormatter


class TestRenderSpending:
    """Tests for spending summary rendering."""

    def test_render_spending_basic(self):
        """Renders spending summary."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "spending": {
                    "period": "monthly",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-27",
                    "total_spending": 450.00,
                    "receipt_count": 8,
                    "item_count": 45,
                    "categories": [
                        {
                            "category": "Produce",
                            "total": 80.00,
                            "percentage": 17.8,
                            "item_count": 15,
                        },
                    ],
                    "budget_limit": None,
                    "budget_remaining": None,
                    "budget_percentage": None,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Spending Summary" in output
        assert "450.00" in output
        assert "Produce" in output

    def test_render_spending_with_budget(self):
        """Renders spending with budget info."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "spending": {
                    "period": "monthly",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-27",
                    "total_spending": 450.00,
                    "receipt_count": 8,
                    "item_count": 45,
                    "categories": [],
                    "budget_limit": 500.00,
                    "budget_remaining": 50.00,
                    "budget_percentage": 90.0,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Budget" in output
        assert "50.00" in output

    def test_render_spending_over_budget(self):
        """Renders spending over budget."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "spending": {
                    "period": "monthly",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-27",
                    "total_spending": 550.00,
                    "receipt_count": 10,
                    "item_count": 50,
                    "categories": [],
                    "budget_limit": 500.00,
                    "budget_remaining": -50.00,
                    "budget_percentage": 110.0,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "-50.00" in output


class TestRenderPriceComparison:
    """Tests for price comparison rendering."""

    def test_render_comparison(self):
        """Renders price comparison table."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "comparison": {
                    "item_name": "Milk",
                    "stores": {"Giant": 5.49, "TJ": 4.99},
                    "cheapest_store": "TJ",
                    "cheapest_price": 4.99,
                    "savings": 0.50,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Price Comparison" in output
        assert "Milk" in output
        assert "Giant" in output
        assert "TJ" in output
        assert "0.50" in output

    def test_render_comparison_no_savings(self):
        """Renders comparison with no savings."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "comparison": {
                    "item_name": "Milk",
                    "stores": {"Giant": 5.49},
                    "cheapest_store": "Giant",
                    "cheapest_price": 5.49,
                    "savings": 0.0,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Price Comparison" in output


class TestRenderSuggestions:
    """Tests for suggestions rendering."""

    def test_render_empty_suggestions(self):
        """Renders empty suggestions."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {"data": {"suggestions": []}}
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "No suggestions" in output

    def test_render_suggestions(self):
        """Renders suggestions list."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "suggestions": [
                    {
                        "type": "restock",
                        "item_name": "Milk",
                        "message": "Usually buy every 5 days",
                        "priority": "high",
                    },
                    {
                        "type": "price_alert",
                        "item_name": "Eggs",
                        "message": "Price up 20%",
                        "priority": "medium",
                    },
                    {
                        "type": "out_of_stock",
                        "item_name": "Oat Milk",
                        "message": "Out of stock 3 times",
                        "priority": "low",
                    },
                ]
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Smart Suggestions" in output
        assert "Milk" in output
        assert "Eggs" in output
        assert "Oat Milk" in output


class TestRenderOutOfStock:
    """Tests for out-of-stock rendering."""

    def test_render_empty(self):
        """Renders empty out-of-stock list."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {"data": {"out_of_stock": []}}
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "No out-of-stock" in output

    def test_render_records(self):
        """Renders out-of-stock records."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "out_of_stock": [
                    {
                        "item_name": "Oat Milk",
                        "store": "Giant",
                        "recorded_date": "2026-01-25",
                        "substitution": "Almond Milk",
                    },
                    {
                        "item_name": "Eggs",
                        "store": "TJ",
                        "recorded_date": "2026-01-26",
                        "substitution": None,
                    },
                ]
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Out of Stock" in output
        assert "Oat Milk" in output
        assert "Almond Milk" in output


class TestRenderFrequency:
    """Tests for frequency data rendering."""

    def test_render_frequency(self):
        """Renders frequency data."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "frequency": {
                    "item_name": "Milk",
                    "average_days": 5.0,
                    "last_purchased": "2026-01-22",
                    "days_since": 5,
                    "next_expected": "2026-01-27",
                    "confidence": "medium",
                    "total_purchases": 7,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Purchase Frequency" in output
        assert "Milk" in output
        assert "5.0" in output
        assert "medium" in output

    def test_render_frequency_no_average(self):
        """Renders frequency data with missing optional fields."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "frequency": {
                    "item_name": "Bread",
                    "average_days": None,
                    "last_purchased": None,
                    "days_since": None,
                    "next_expected": None,
                    "confidence": "low",
                    "total_purchases": 1,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Bread" in output
        assert "low" in output
