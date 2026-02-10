"""Output formatting for CLI and programmatic use."""

import json
from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for output."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.isoformat()
        return super().default(obj)


class OutputFormatter:
    """Formats output for both Rich terminal and JSON modes."""

    def __init__(self, json_mode: bool = False):
        """Initialize formatter.

        Args:
            json_mode: If True, output JSON instead of Rich formatting
        """
        self.json_mode = json_mode
        self.console = Console()

    def output(self, data: dict[str, Any], message: str = "") -> None:
        """Output data in appropriate format.

        Args:
            data: Data to output
            message: Optional message for Rich mode
        """
        if self.json_mode:
            self._output_json(data)
        else:
            self._output_rich(data, message)

    def _output_json(self, data: dict[str, Any]) -> None:
        """Output as JSON to stdout."""
        print(json.dumps(data, cls=JSONEncoder, indent=2))

    def _output_rich(self, data: dict[str, Any], message: str) -> None:
        """Output with Rich formatting."""
        if message:
            self.console.print(f"[green]✓[/green] {message}")

        # Format based on data type
        if "list" in data.get("data", {}):
            self._render_grocery_list(data)
        elif "receipt" in data.get("data", {}):
            self._render_receipt(data)
        elif "reconciliation" in data.get("data", {}):
            self._render_reconciliation(data)
        elif "price_points" in data.get("data", {}):
            self._render_price_history(data)
        elif "item" in data.get("data", {}) and isinstance(data["data"]["item"], dict):
            self._render_item(data)
        elif "by_store" in data.get("data", {}):
            self._render_by_store(data)
        elif "by_category" in data.get("data", {}):
            self._render_by_category(data)
        elif "spending" in data.get("data", {}):
            self._render_spending(data)
        elif "comparison" in data.get("data", {}):
            self._render_price_comparison(data)
        elif "recommendation" in data.get("data", {}):
            self._render_recommendation(data)
        elif "suggestions" in data.get("data", {}):
            self._render_suggestions(data)
        elif "out_of_stock" in data.get("data", {}):
            self._render_out_of_stock(data)
        elif "frequency" in data.get("data", {}):
            self._render_frequency(data)
        elif "inventory_item" in data.get("data", {}):
            self._render_inventory_item(data)
        elif "inventory" in data.get("data", {}):
            self._render_inventory(data)
        elif "expiring" in data.get("data", {}):
            self._render_expiring(data)
        elif "low_stock" in data.get("data", {}):
            self._render_low_stock(data)
        elif "waste_log" in data.get("data", {}):
            self._render_waste_log(data)
        elif "waste_summary" in data.get("data", {}):
            self._render_waste_summary(data)
        elif "budget_status" in data.get("data", {}):
            self._render_budget_status(data)
        elif "preferences" in data.get("data", {}):
            self._render_preferences(data)

    def _render_grocery_list(self, data: dict) -> None:
        """Render grocery list with Rich."""
        list_data = data["data"]["list"]
        items = list_data["items"]

        if not items:
            self.console.print("[dim]No items on the list[/dim]")
            return

        table = Table(title="Grocery List", show_header=True, header_style="bold cyan")
        table.add_column("Item", style="cyan", no_wrap=False)
        table.add_column("Qty", style="magenta", justify="right")
        table.add_column("Store", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Status", style="blue")

        for item in items:
            status_icon = {
                "to_buy": "[white]\u25cb[/white]",
                "bought": "[green]\u2713[/green]",
                "still_needed": "[yellow]\u25cb[/yellow]",
            }.get(item.get("status", "to_buy"), "\u25cb")

            table.add_row(
                item["name"],
                str(item.get("quantity", 1)),
                item.get("store") or "-",
                item.get("category", "Other"),
                status_icon,
            )

        self.console.print(table)
        self.console.print(f"\nTotal items: {len(items)}")

    def _render_item(self, data: dict) -> None:
        """Render a single item with Rich."""
        item = data["data"]["item"]

        panel_content = f"""[bold]{item["name"]}[/bold]

Quantity: {item.get("quantity", 1)} {item.get("unit") or ""}
Store: {item.get("store") or "Not specified"}
Category: {item.get("category", "Other")}
Priority: {item.get("priority", "medium")}
Status: {item.get("status", "to_buy")}"""

        if item.get("brand_preference"):
            panel_content += f"\nBrand: {item['brand_preference']}"

        if item.get("estimated_price"):
            panel_content += f"\nEst. Price: ${item['estimated_price']:.2f}"

        if item.get("notes"):
            panel_content += f"\nNotes: {item['notes']}"

        panel = Panel(panel_content, title="Item Details", border_style="green")
        self.console.print(panel)

    def _render_receipt(self, data: dict) -> None:
        """Render receipt summary with Rich."""
        receipt = data["data"]["receipt"]

        panel = Panel(
            f"""[bold]{receipt["store_name"]}[/bold]

Date: {receipt["transaction_date"]} {receipt.get("transaction_time", "")}
Items: {len(receipt["line_items"])}
Total: ${receipt["total"]:.2f}""",
            title="Receipt Processed",
            border_style="green",
        )

        self.console.print(panel)

        # Show items table
        table = Table(show_header=True)
        table.add_column("Item")
        table.add_column("Qty", justify="right")
        table.add_column("Price", justify="right")

        for item in receipt["line_items"]:
            table.add_row(
                item["item_name"],
                str(item["quantity"]),
                f"${item['total_price']:.2f}",
            )

        self.console.print(table)

    def _render_reconciliation(self, data: dict) -> None:
        """Render reconciliation results."""
        recon = data["data"]["reconciliation"]

        self.console.print("\n[bold]Reconciliation Summary[/bold]")
        self.console.print(f"Items purchased: {recon['items_purchased']}")
        self.console.print(f"Total spent: ${recon['total_spent']:.2f}")
        self.console.print(f"Matched from list: {recon['matched_items']}")

        if recon.get("still_needed"):
            self.console.print(f"\n[yellow]Still needed ({len(recon['still_needed'])}):[/yellow]")
            for item in recon["still_needed"]:
                self.console.print(f"  - {item}")

        if recon.get("newly_bought"):
            self.console.print(
                f"\n[blue]New items not on list ({len(recon['newly_bought'])}):[/blue]"
            )
            for item in recon["newly_bought"]:
                self.console.print(f"  - {item}")

    def _render_by_store(self, data: dict) -> None:
        """Render items grouped by store."""
        by_store = data["data"]["by_store"]

        for store, items in by_store.items():
            self.console.print(f"\n[bold cyan]{store}[/bold cyan]")
            for item in items:
                self.console.print(f"  - {item['name']} ({item.get('quantity', 1)})")

    def _render_by_category(self, data: dict) -> None:
        """Render items grouped by category."""
        by_category = data["data"]["by_category"]

        for category, items in by_category.items():
            self.console.print(f"\n[bold yellow]{category}[/bold yellow]")
            for item in items:
                self.console.print(f"  - {item['name']} ({item.get('quantity', 1)})")

    def _render_price_history(self, data: dict) -> None:
        """Render price history."""
        price_data = data["data"]

        self.console.print(f"\n[bold]Price History: {price_data['item']}[/bold]")
        self.console.print(f"Store: {price_data['store']}")

        if price_data.get("current_price") is not None:
            self.console.print(f"Current: ${price_data['current_price']:.2f}")
        if price_data.get("average_price") is not None:
            self.console.print(f"Average: ${price_data['average_price']:.2f}")
        if price_data.get("lowest_price") is not None:
            self.console.print(f"Lowest: ${price_data['lowest_price']:.2f}")
        if price_data.get("highest_price") is not None:
            self.console.print(f"Highest: ${price_data['highest_price']:.2f}")

        if price_data.get("price_points"):
            self.console.print("\n[dim]Recent prices:[/dim]")
            for pp in price_data["price_points"][-5:]:  # Show last 5
                sale_marker = " [yellow](sale)[/yellow]" if pp.get("sale") else ""
                self.console.print(f"  {pp['date']}: ${pp['price']:.2f}{sale_marker}")

    def _render_spending(self, data: dict) -> None:
        """Render spending summary."""
        spending = data["data"]["spending"]

        self.console.print(f"\n[bold]Spending Summary ({spending['period']})[/bold]")
        self.console.print(f"Period: {spending['start_date']} to {spending['end_date']}")
        self.console.print(f"Total spent: ${spending['total_spending']:.2f}")
        self.console.print(f"Receipts: {spending['receipt_count']}")
        self.console.print(f"Items purchased: {spending['item_count']}")

        if spending.get("budget_limit") is not None:
            self.console.print(
                f"\nBudget: ${spending['total_spending']:.2f} / ${spending['budget_limit']:.2f}"
            )
            remaining = spending.get("budget_remaining", 0)
            pct = spending.get("budget_percentage", 0)
            color = "green" if remaining > 0 else "red"
            self.console.print(f"Remaining: [{color}]${remaining:.2f}[/{color}] ({pct:.1f}% used)")

        if spending.get("categories"):
            self.console.print("\n[dim]By category:[/dim]")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Category")
            table.add_column("Amount", justify="right")
            table.add_column("%", justify="right")
            table.add_column("Items", justify="right")

            for cat in spending["categories"]:
                table.add_row(
                    cat["category"],
                    f"${cat['total']:.2f}",
                    f"{cat['percentage']:.1f}%",
                    str(cat["item_count"]),
                )
            self.console.print(table)

        if spending.get("category_inflation"):
            self.console.print("\n[dim]Category inflation:[/dim]")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Category")
            table.add_column("Baseline", justify="right")
            table.add_column("Current", justify="right")
            table.add_column("Delta", justify="right")
            table.add_column("Windows")

            for row in spending["category_inflation"]:
                delta = row.get("delta_pct")
                delta_display = f"{delta:+.1f}%" if delta is not None else "n/a"
                windows = (
                    f"{row.get('baseline_start')}..{row.get('baseline_end')} vs "
                    f"{row.get('current_start')}..{row.get('current_end')}"
                )
                table.add_row(
                    row["category"],
                    f"${row.get('baseline_avg_price', 0):.2f}",
                    f"${row.get('current_avg_price', 0):.2f}",
                    delta_display,
                    windows,
                )
            self.console.print(table)

    def _render_price_comparison(self, data: dict) -> None:
        """Render price comparison across stores."""
        comp = data["data"]["comparison"]

        self.console.print(f"\n[bold]Price Comparison: {comp['item_name']}[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Store")
        table.add_column("Price", justify="right")
        table.add_column("", justify="center")

        for store, price in sorted(comp["stores"].items(), key=lambda x: x[1]):
            marker = " [green](best)[/green]" if store == comp.get("cheapest_store") else ""
            table.add_row(store, f"${price:.2f}", marker)

        self.console.print(table)

        if comp.get("average_price_30d") is not None:
            self.console.print(f"30d avg: ${comp['average_price_30d']:.2f}")
        if comp.get("average_price_90d") is not None:
            self.console.print(f"90d avg: ${comp['average_price_90d']:.2f}")
        if comp.get("delta_vs_30d_pct") is not None:
            self.console.print(f"Delta vs 30d: {comp['delta_vs_30d_pct']:+.1f}%")
        if comp.get("delta_vs_90d_pct") is not None:
            self.console.print(f"Delta vs 90d: {comp['delta_vs_90d_pct']:+.1f}%")

        if comp.get("savings") and comp["savings"] > 0:
            self.console.print(
                f"\nPotential savings: [green]${comp['savings']:.2f}[/green] "
                f"by buying at {comp['cheapest_store']}"
            )

    def _render_recommendation(self, data: dict) -> None:
        """Render item store recommendation."""
        rec = data["data"]["recommendation"]

        self.console.print(f"\n[bold]Store Recommendation: {rec['item_name']}[/bold]")
        self.console.print(
            f"Recommended store: [green]{rec.get('recommended_store') or '-'}[/green]"
        )
        self.console.print(
            f"Confidence: {rec.get('confidence', 'low')} ({rec.get('confidence_score', 0):.2f})"
        )

        ranked_stores = rec.get("ranked_stores", [])
        if ranked_stores:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Rank", justify="right")
            table.add_column("Store")
            table.add_column("Score", justify="right")
            table.add_column("Current", justify="right")
            table.add_column("Avg", justify="right")
            table.add_column("OOS", justify="right")
            table.add_column("Notes")

            for row in ranked_stores:
                table.add_row(
                    str(row.get("rank", "")),
                    row.get("store", "-"),
                    f"{row.get('score', 0):.3f}",
                    f"${row.get('current_price', 0):.2f}",
                    f"${row.get('average_price', 0):.2f}",
                    str(row.get("out_of_stock_count", 0)),
                    "; ".join(row.get("rationale", [])) or "-",
                )
            self.console.print(table)

        substitutions = rec.get("substitutions", [])
        if substitutions:
            sub_table = Table(show_header=True, header_style="bold")
            sub_table.add_column("Substitute")
            sub_table.add_column("Count", justify="right")
            sub_table.add_column("Stores")

            for sub in substitutions:
                sub_table.add_row(
                    sub.get("item_name", "-"),
                    str(sub.get("count", 0)),
                    ", ".join(sub.get("stores", [])) or "-",
                )

            self.console.print("\n[dim]Substitution history:[/dim]")
            self.console.print(sub_table)

        if rec.get("rationale"):
            self.console.print("\n[dim]Why:[/dim]")
            for reason in rec["rationale"]:
                self.console.print(f"  - {reason}")

    def _render_suggestions(self, data: dict) -> None:
        """Render smart suggestions."""
        suggestions = data["data"]["suggestions"]

        if not suggestions:
            self.console.print("[dim]No suggestions at this time[/dim]")
            return

        self.console.print("\n[bold]Smart Suggestions[/bold]")

        for s in suggestions:
            icon = {"restock": "\u26a0", "price_alert": "$", "out_of_stock": "\u2717"}.get(
                s["type"], "\u2022"
            )
            priority_color = {
                "high": "red",
                "medium": "yellow",
                "low": "dim",
            }.get(s["priority"], "white")

            self.console.print(
                f"  [{priority_color}]{icon}[/{priority_color}] "
                f"[bold]{s['item_name']}[/bold]: {s['message']}"
            )

    def _render_out_of_stock(self, data: dict) -> None:
        """Render out-of-stock records."""
        records = data["data"]["out_of_stock"]

        if not records:
            self.console.print("[dim]No out-of-stock records[/dim]")
            return

        self.console.print("\n[bold]Out of Stock Records[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Item")
        table.add_column("Store")
        table.add_column("Date")
        table.add_column("Substitution")

        for record in records:
            table.add_row(
                record["item_name"],
                record["store"],
                str(record.get("recorded_date", "")),
                record.get("substitution") or "-",
            )

        self.console.print(table)

    def _render_frequency(self, data: dict) -> None:
        """Render frequency data for an item."""
        freq = data["data"]["frequency"]

        self.console.print(f"\n[bold]Purchase Frequency: {freq['item_name']}[/bold]")

        if freq.get("average_days") is not None:
            self.console.print(f"Average interval: {freq['average_days']:.1f} days")
        if freq.get("last_purchased"):
            self.console.print(f"Last purchased: {freq['last_purchased']}")
        if freq.get("days_since") is not None:
            self.console.print(f"Days since last purchase: {freq['days_since']}")
        if freq.get("next_expected"):
            self.console.print(f"Next expected: {freq['next_expected']}")
        self.console.print(f"Confidence: {freq.get('confidence', 'low')}")
        self.console.print(f"Total purchases: {freq.get('total_purchases', 0)}")

    def _render_inventory_item(self, data: dict) -> None:
        """Render a single inventory item."""
        item = data["data"]["inventory_item"]
        self.console.print(
            f"  {item['item_name']} — qty: {item.get('quantity', 1)}, "
            f"location: {item.get('location', 'pantry')}"
        )

    def _render_inventory(self, data: dict) -> None:
        """Render inventory list."""
        items = data["data"]["inventory"]

        if not items:
            self.console.print("[dim]No items in inventory[/dim]")
            return

        table = Table(title="Household Inventory", show_header=True, header_style="bold cyan")
        table.add_column("Item", style="cyan")
        table.add_column("Qty", justify="right")
        table.add_column("Location", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Expires", style="red")

        for item in items:
            exp = str(item.get("expiration_date", "")) if item.get("expiration_date") else "-"
            table.add_row(
                item["item_name"],
                str(item.get("quantity", 1)),
                item.get("location", "pantry"),
                item.get("category", "Other"),
                exp,
            )

        self.console.print(table)

    def _render_expiring(self, data: dict) -> None:
        """Render expiring items."""
        items = data["data"]["expiring"]
        days = data["data"].get("days", 3)

        if not items:
            self.console.print(f"[dim]No items expiring within {days} days[/dim]")
            return

        self.console.print(f"\n[bold red]Items Expiring Within {days} Days[/bold red]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Item")
        table.add_column("Expires", style="red")
        table.add_column("Location")
        table.add_column("Qty", justify="right")

        for item in items:
            table.add_row(
                item["item_name"],
                str(item.get("expiration_date", "")),
                item.get("location", ""),
                str(item.get("quantity", 1)),
            )

        self.console.print(table)

    def _render_low_stock(self, data: dict) -> None:
        """Render low stock items."""
        items = data["data"]["low_stock"]

        if not items:
            self.console.print("[dim]No items are low on stock[/dim]")
            return

        self.console.print("\n[bold yellow]Low Stock Items[/bold yellow]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Item")
        table.add_column("Qty", justify="right", style="red")
        table.add_column("Threshold", justify="right")
        table.add_column("Location")

        for item in items:
            table.add_row(
                item["item_name"],
                str(item.get("quantity", 0)),
                str(item.get("low_stock_threshold", 1)),
                item.get("location", ""),
            )

        self.console.print(table)

    def _render_waste_log(self, data: dict) -> None:
        """Render waste log records."""
        records = data["data"]["waste_log"]

        if not records:
            self.console.print("[dim]No waste records[/dim]")
            return

        self.console.print("\n[bold]Waste Log[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Item")
        table.add_column("Qty", justify="right")
        table.add_column("Reason")
        table.add_column("Cost", justify="right")
        table.add_column("Date")

        for record in records:
            cost = f"${record['estimated_cost']:.2f}" if record.get("estimated_cost") else "-"
            table.add_row(
                record["item_name"],
                str(record.get("quantity", 1)),
                record.get("reason", "other"),
                cost,
                str(record.get("waste_logged_date", "")),
            )

        self.console.print(table)

    def _render_waste_summary(self, data: dict) -> None:
        """Render waste summary with insights."""
        summary = data["data"]["waste_summary"]
        insights = data["data"].get("insights", [])

        self.console.print(f"\n[bold]Waste Summary ({summary['period']})[/bold]")
        self.console.print(f"Period: {summary['start_date']} to {summary['end_date']}")
        self.console.print(f"Items wasted: {summary['total_items_wasted']}")
        self.console.print(f"Total cost: ${summary['total_cost']:.2f}")

        if summary.get("by_reason"):
            self.console.print("\n[dim]By reason:[/dim]")
            for reason, count in summary["by_reason"].items():
                self.console.print(f"  {reason}: {count}")

        if summary.get("most_wasted"):
            self.console.print("\n[dim]Most wasted:[/dim]")
            for entry in summary["most_wasted"]:
                self.console.print(f"  {entry['item']}: {entry['count']} times")

        if insights:
            self.console.print("\n[bold yellow]Insights[/bold yellow]")
            for insight in insights:
                self.console.print(f"  💡 {insight}")

    def _render_budget_status(self, data: dict) -> None:
        """Render budget status."""
        budget = data["data"]["budget_status"]

        self.console.print(f"\n[bold]Budget Status — {budget['month']}[/bold]")

        limit = budget.get("monthly_limit", 0)
        spent = budget.get("total_spent", 0)
        remaining = limit - spent
        color = "green" if remaining >= 0 else "red"

        self.console.print(f"Budget: ${limit:.2f}")
        self.console.print(f"Spent: ${spent:.2f}")
        self.console.print(f"Remaining: [{color}]${remaining:.2f}[/{color}]")

        if budget.get("category_budgets"):
            self.console.print("\n[dim]By category:[/dim]")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Category")
            table.add_column("Limit", justify="right")
            table.add_column("Spent", justify="right")
            table.add_column("Remaining", justify="right")

            for cb in budget["category_budgets"]:
                cb_remaining = cb.get("limit", 0) - cb.get("spent", 0)
                cb_color = "green" if cb_remaining >= 0 else "red"
                table.add_row(
                    cb["category"],
                    f"${cb.get('limit', 0):.2f}",
                    f"${cb.get('spent', 0):.2f}",
                    f"[{cb_color}]${cb_remaining:.2f}[/{cb_color}]",
                )
            self.console.print(table)

    def _render_preferences(self, data: dict) -> None:
        """Render user preferences."""
        prefs = data["data"]["preferences"]

        self.console.print(f"\n[bold]Preferences: {prefs['user']}[/bold]")

        if prefs.get("brand_preferences"):
            self.console.print("\n[dim]Brand preferences:[/dim]")
            for item, brand in prefs["brand_preferences"].items():
                self.console.print(f"  {item}: {brand}")

        if prefs.get("dietary_restrictions"):
            self.console.print(f"\nDietary: {', '.join(prefs['dietary_restrictions'])}")

        if prefs.get("allergens"):
            self.console.print(f"Allergens: [red]{', '.join(prefs['allergens'])}[/red]")

        if prefs.get("favorite_items"):
            self.console.print(f"Favorites: {', '.join(prefs['favorite_items'])}")

    def error(self, message: str, error_code: str | None = None) -> None:
        """Output error message.

        Args:
            message: Error message
            error_code: Optional error code
        """
        if self.json_mode:
            output = {"success": False, "error": message}
            if error_code:
                output["error_code"] = error_code
            print(json.dumps(output))
        else:
            self.console.print(f"[red]\u2717 Error:[/red] {message}")

    def success(self, message: str, data: dict | None = None) -> None:
        """Output success message.

        Args:
            message: Success message
            data: Optional data to include
        """
        if self.json_mode:
            output: dict[str, Any] = {"success": True, "message": message}
            if data:
                output["data"] = data
            print(json.dumps(output, cls=JSONEncoder))
        else:
            self.console.print(f"[green]\u2713[/green] {message}")

    def warning(self, message: str) -> None:
        """Output warning message.

        Args:
            message: Warning message
        """
        if self.json_mode:
            print(json.dumps({"warning": message}))
        else:
            self.console.print(f"[yellow]\u26a0[/yellow] {message}")
