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

    def test_render_spending_with_inflation_table(self):
        """Renders category inflation details when present."""
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
                    "category_inflation": [
                        {
                            "category": "Dairy & Eggs",
                            "baseline_start": "2026-01-01",
                            "baseline_end": "2026-01-14",
                            "current_start": "2026-01-15",
                            "current_end": "2026-01-27",
                            "baseline_avg_price": 4.20,
                            "current_avg_price": 5.00,
                            "delta_pct": 19.0,
                            "baseline_samples": 3,
                            "current_samples": 4,
                        }
                    ],
                    "budget_limit": None,
                    "budget_remaining": None,
                    "budget_percentage": None,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Category inflation" in output
        assert "Dairy & Eggs" in output
        assert "19.0%" in output


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

    def test_render_comparison_with_window_metrics(self):
        """Renders 30d/90d metrics when present."""
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
                    "average_price_30d": 5.10,
                    "average_price_90d": 4.90,
                    "delta_vs_30d_pct": -2.2,
                    "delta_vs_90d_pct": 1.8,
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "30d avg" in output
        assert "90d avg" in output
        assert "Delta vs 30d" in output


class TestRenderSavings:
    """Tests for savings summary rendering."""

    def test_render_savings_with_contributors(self):
        """Renders savings totals and contributor tables."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "savings": {
                    "period": "monthly",
                    "start_date": "2026-02-01",
                    "end_date": "2026-02-10",
                    "total_savings": 12.5,
                    "receipt_count": 3,
                    "record_count": 5,
                    "top_items": [
                        {"name": "Milk", "total_savings": 6.0, "record_count": 2},
                    ],
                    "top_stores": [
                        {"name": "Giant", "total_savings": 8.0, "record_count": 3},
                    ],
                    "top_categories": [
                        {"name": "Dairy & Eggs", "total_savings": 9.0, "record_count": 3},
                    ],
                    "by_source": [
                        {"name": "line_item_discount", "total_savings": 7.0, "record_count": 2},
                    ],
                    "assumptions": ["Line-item savings use explicit discounts."],
                }
            }
        }

        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Savings Summary" in output
        assert "12.50" in output
        assert "Milk" in output
        assert "line_item_discount" in output


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
                    {
                        "type": "seasonal_optimization",
                        "item_name": "Strawberries",
                        "message": "Current price is 2.0x seasonal baseline",
                        "priority": "medium",
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
        assert "Strawberries" in output


class TestRenderRecommendation:
    """Tests for recommendation rendering."""

    def test_render_recommendation(self):
        """Renders recommendation table and substitution history."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "recommendation": {
                    "item_name": "Milk",
                    "recommended_store": "TJ",
                    "confidence": "high",
                    "confidence_score": 0.82,
                    "ranked_stores": [
                        {
                            "store": "TJ",
                            "rank": 1,
                            "score": 0.82,
                            "current_price": 4.99,
                            "average_price": 5.10,
                            "out_of_stock_count": 0,
                            "rationale": ["Lowest current price.", "Recent price data."],
                        },
                        {
                            "store": "Giant",
                            "rank": 2,
                            "score": 0.66,
                            "current_price": 5.49,
                            "average_price": 5.39,
                            "out_of_stock_count": 1,
                            "rationale": ["1 out-of-stock reports."],
                        },
                    ],
                    "substitutions": [
                        {"item_name": "Oat Milk", "count": 2, "stores": ["Giant", "TJ"]}
                    ],
                    "rationale": [
                        "Ranking uses price, recency, sample depth, and out-of-stock history."
                    ],
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Store Recommendation" in output
        assert "Confidence" in output
        assert "TJ" in output
        assert "Substitution history" in output
        assert "Oat Milk" in output


class TestRenderRoute:
    """Tests for route rendering."""

    def test_render_route_empty(self):
        """Renders empty route summary and zero-stop state."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "route": {
                    "total_items": 0,
                    "total_estimated_cost": 0.0,
                    "stops": [],
                    "unassigned_items": [],
                    "rationale": [],
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Shopping Route" in output
        assert "No store stops available" in output

    def test_render_route_with_stops(self):
        """Renders shopping route table and item details."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "route": {
                    "total_items": 3,
                    "total_estimated_cost": 14.27,
                    "stops": [
                        {
                            "stop_number": 1,
                            "store": "Giant",
                            "item_count": 2,
                            "estimated_total": 9.48,
                            "items": [
                                {
                                    "item_name": "Milk",
                                    "quantity": 1,
                                    "assignment_source": "recommendation",
                                    "estimated_price": 4.99,
                                },
                                {
                                    "item_name": "Bread",
                                    "quantity": 1,
                                    "assignment_source": "list_preference",
                                    "estimated_price": 4.49,
                                },
                            ],
                        },
                        {
                            "stop_number": 2,
                            "store": "TJ",
                            "item_count": 1,
                            "estimated_total": 4.79,
                            "items": [
                                {
                                    "item_name": "Eggs",
                                    "quantity": 1,
                                    "assignment_source": "recommendation",
                                    "estimated_price": 4.79,
                                }
                            ],
                        },
                    ],
                    "unassigned_items": [],
                    "rationale": [
                        "Store order is deterministic: item priority, item count, then store name."
                    ],
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Shopping Route" in output
        assert "Giant" in output
        assert "TJ" in output
        assert "Milk" in output

    def test_render_route_with_unassigned(self):
        """Renders unassigned item section."""
        fmt = OutputFormatter(json_mode=False)
        fmt.console = Console(file=StringIO())
        data = {
            "data": {
                "route": {
                    "total_items": 1,
                    "total_estimated_cost": 0.0,
                    "stops": [],
                    "unassigned_items": [{"item_name": "Paprika"}],
                    "rationale": [],
                }
            }
        }
        fmt.output(data)
        output = fmt.console.file.getvalue()
        assert "Needs store assignment" in output
        assert "Paprika" in output


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
