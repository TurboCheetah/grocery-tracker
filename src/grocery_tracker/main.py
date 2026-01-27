"""CLI entry point for Grocery Tracker."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .analytics import Analytics
from .data_store import DataStore
from .list_manager import DuplicateItemError, ItemNotFoundError, ListManager
from .models import ItemStatus, Priority
from .output_formatter import OutputFormatter
from .receipt_processor import ReceiptProcessor

app = typer.Typer(
    name="grocery",
    help="Intelligent grocery list and inventory management",
    no_args_is_help=True,
)

console = Console()

# Global state for formatter (set by callback)
formatter: OutputFormatter = OutputFormatter()
data_store: DataStore | None = None
list_manager: ListManager | None = None


def get_data_store() -> DataStore:
    """Get or create DataStore instance."""
    global data_store
    if data_store is None:
        data_store = DataStore()
    return data_store


def get_list_manager() -> ListManager:
    """Get or create ListManager instance."""
    global list_manager
    if list_manager is None:
        list_manager = ListManager(get_data_store())
    return list_manager


@app.callback()
def main(
    json_output: Annotated[
        bool, typer.Option("--json", help="Output as JSON for programmatic use")
    ] = False,
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="Data directory path")] = None,
) -> None:
    """Grocery Tracker CLI - Manage your grocery lists with intelligence."""
    global formatter, data_store, list_manager

    formatter = OutputFormatter(json_mode=json_output)

    if data_dir:
        data_store = DataStore(data_dir=data_dir)
        list_manager = ListManager(data_store)


@app.command()
def add(
    item: Annotated[str, typer.Argument(help="Item name to add")],
    quantity: Annotated[float, typer.Option("--quantity", "-q", help="Quantity to buy")] = 1,
    store: Annotated[str | None, typer.Option("--store", "-s", help="Store to buy from")] = None,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Product category")
    ] = None,
    unit: Annotated[str | None, typer.Option("--unit", "-u", help="Unit of measurement")] = None,
    brand: Annotated[str | None, typer.Option("--brand", "-b", help="Preferred brand")] = None,
    price: Annotated[float | None, typer.Option("--price", "-p", help="Estimated price")] = None,
    priority: Annotated[
        Priority, typer.Option("--priority", help="Item priority")
    ] = Priority.MEDIUM,
    added_by: Annotated[str | None, typer.Option("--by", help="Person adding the item")] = None,
    notes: Annotated[str | None, typer.Option("--notes", "-n", help="Additional notes")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Allow duplicate items")] = False,
) -> None:
    """Add an item to the grocery list."""
    try:
        manager = get_list_manager()
        result = manager.add_item(
            name=item,
            quantity=quantity,
            store=store,
            category=category,
            unit=unit,
            brand_preference=brand,
            estimated_price=price,
            priority=priority,
            added_by=added_by,
            notes=notes,
            allow_duplicate=force,
        )
        formatter.output(result, result["message"])
    except DuplicateItemError as e:
        formatter.error(str(e), error_code="DUPLICATE_ITEM")
        raise typer.Exit(code=1)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@app.command()
def remove(
    item_id: Annotated[str, typer.Argument(help="Item ID to remove")],
) -> None:
    """Remove an item from the grocery list."""
    try:
        manager = get_list_manager()
        result = manager.remove_item(item_id)
        formatter.output(result, result["message"])
    except ItemNotFoundError as e:
        formatter.error(str(e), error_code="ITEM_NOT_FOUND")
        raise typer.Exit(code=1)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@app.command(name="list")
def list_items(
    store: Annotated[str | None, typer.Option("--store", "-s", help="Filter by store")] = None,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Filter by category")
    ] = None,
    status: Annotated[ItemStatus | None, typer.Option("--status", help="Filter by status")] = None,
    by_store: Annotated[bool, typer.Option("--by-store", help="Group by store")] = False,
    by_category: Annotated[bool, typer.Option("--by-category", help="Group by category")] = False,
) -> None:
    """View the grocery list."""
    try:
        manager = get_list_manager()

        if by_store:
            result = manager.get_by_store()
        elif by_category:
            result = manager.get_by_category()
        else:
            result = manager.get_list(store=store, category=category, status=status)

        formatter.output(result)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@app.command()
def bought(
    item_id: Annotated[str, typer.Argument(help="Item ID to mark as bought")],
    quantity: Annotated[
        float | None, typer.Option("--quantity", "-q", help="Actual quantity bought")
    ] = None,
    price: Annotated[float | None, typer.Option("--price", "-p", help="Actual price paid")] = None,
) -> None:
    """Mark an item as bought."""
    try:
        manager = get_list_manager()
        result = manager.mark_bought(item_id, quantity=quantity, price=price)
        formatter.output(result, result["message"])
    except ItemNotFoundError as e:
        formatter.error(str(e), error_code="ITEM_NOT_FOUND")
        raise typer.Exit(code=1)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@app.command()
def update(
    item_id: Annotated[str, typer.Argument(help="Item ID to update")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    quantity: Annotated[float | None, typer.Option("--quantity", "-q", help="New quantity")] = None,
    store: Annotated[str | None, typer.Option("--store", "-s", help="New store")] = None,
    category: Annotated[str | None, typer.Option("--category", "-c", help="New category")] = None,
    unit: Annotated[str | None, typer.Option("--unit", "-u", help="New unit")] = None,
    brand: Annotated[str | None, typer.Option("--brand", "-b", help="New brand")] = None,
    price: Annotated[float | None, typer.Option("--price", "-p", help="New price")] = None,
    priority: Annotated[Priority | None, typer.Option("--priority", help="New priority")] = None,
    notes: Annotated[str | None, typer.Option("--notes", "-n", help="New notes")] = None,
    status: Annotated[ItemStatus | None, typer.Option("--status", help="New status")] = None,
) -> None:
    """Update an existing item."""
    try:
        manager = get_list_manager()
        result = manager.update_item(
            item_id=item_id,
            name=name,
            quantity=quantity,
            store=store,
            category=category,
            unit=unit,
            brand_preference=brand,
            estimated_price=price,
            priority=priority,
            notes=notes,
            status=status,
        )
        formatter.output(result, result["message"])
    except ItemNotFoundError as e:
        formatter.error(str(e), error_code="ITEM_NOT_FOUND")
        raise typer.Exit(code=1)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@app.command()
def clear(
    bought_only: Annotated[
        bool, typer.Option("--bought/--all", help="Only clear bought items, or all items")
    ] = True,
) -> None:
    """Clear items from the list."""
    try:
        manager = get_list_manager()
        if bought_only:
            result = manager.clear_bought()
            formatter.success(result["message"], result.get("data"))
        else:
            formatter.error("Use --bought to clear bought items, or --all to clear everything")
            raise typer.Exit(code=1)
    except SystemExit:
        raise
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


# Receipt subcommand group
receipt_app = typer.Typer(help="Receipt processing commands")
app.add_typer(receipt_app, name="receipt")


@receipt_app.command("process")
def process_receipt(
    data: Annotated[str | None, typer.Option("--data", "-d", help="JSON receipt data")] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Path to JSON file")] = None,
) -> None:
    """Process receipt data and reconcile with shopping list."""
    try:
        if not data and not file:
            formatter.error("Must provide either --data or --file")
            raise typer.Exit(code=1)

        if data:
            receipt_dict = json.loads(data)
        else:
            with open(file) as f:  # type: ignore[arg-type]
                receipt_dict = json.load(f)

        processor = ReceiptProcessor(
            list_manager=get_list_manager(),
            data_store=get_data_store(),
        )

        result = processor.process_receipt_dict(receipt_dict)

        output_data = {
            "success": True,
            "data": {
                "receipt": receipt_dict,
                "reconciliation": result.model_dump(),
            },
        }

        formatter.output(output_data, f"Processed receipt from {receipt_dict['store_name']}")
    except json.JSONDecodeError as e:
        formatter.error(f"Invalid JSON: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@receipt_app.command("list")
def list_receipts() -> None:
    """List all processed receipts."""
    try:
        store = get_data_store()
        receipts = store.list_receipts()

        if not receipts:
            formatter.warning("No receipts found")
            return

        output_data = {
            "success": True,
            "data": {
                "receipts": [
                    {
                        "id": str(r.id),
                        "store": r.store_name,
                        "date": r.transaction_date.isoformat(),
                        "total": r.total,
                        "items": len(r.line_items),
                    }
                    for r in receipts
                ]
            },
        }

        formatter.output(output_data, f"Found {len(receipts)} receipts")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


# Price subcommand group
price_app = typer.Typer(help="Price history commands")
app.add_typer(price_app, name="price")


@price_app.command("history")
def price_history(
    item: Annotated[str, typer.Argument(help="Item name")],
    store: Annotated[str | None, typer.Option("--store", "-s", help="Filter by store")] = None,
) -> None:
    """View price history for an item."""
    try:
        store_instance = get_data_store()
        history = store_instance.get_price_history(item, store)

        if not history:
            formatter.warning(f"No price history found for '{item}'")
            return

        output_data = {
            "success": True,
            "data": {
                "item": item,
                "store": store or "all",
                "current_price": history.current_price,
                "average_price": history.average_price,
                "lowest_price": history.lowest_price,
                "highest_price": history.highest_price,
                "price_points": [
                    {
                        "date": p.date.isoformat(),
                        "price": p.price,
                        "sale": p.sale,
                    }
                    for p in history.price_points
                ],
            },
        }

        formatter.output(output_data, f"Price history for {item}")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


# Stats subcommand group
stats_app = typer.Typer(help="Spending analytics and insights")
app.add_typer(stats_app, name="stats")


@stats_app.callback(invoke_without_command=True)
def stats_default(
    ctx: typer.Context,
    period: Annotated[
        str, typer.Option("--period", "-p", help="Period: weekly, monthly, yearly")
    ] = "monthly",
    budget: Annotated[
        float | None, typer.Option("--budget", "-b", help="Budget limit for comparison")
    ] = None,
) -> None:
    """View spending analytics. Defaults to monthly summary."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        analytics = Analytics(data_store=get_data_store())
        summary = analytics.spending_summary(period=period, budget_limit=budget)

        output_data = {
            "success": True,
            "data": {
                "spending": summary.model_dump(),
            },
        }
        formatter.output(output_data, f"Spending summary ({period})")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@stats_app.command("frequency")
def stats_frequency(
    item: Annotated[str, typer.Argument(help="Item name")],
) -> None:
    """View purchase frequency for an item."""
    try:
        analytics = Analytics(data_store=get_data_store())
        freq = analytics.get_frequency_summary(item)

        if not freq:
            formatter.warning(f"No purchase frequency data for '{item}'")
            return

        output_data = {
            "success": True,
            "data": {
                "frequency": {
                    "item_name": freq.item_name,
                    "category": freq.category,
                    "average_days": freq.average_days_between_purchases,
                    "last_purchased": freq.last_purchased.isoformat()
                    if freq.last_purchased
                    else None,
                    "days_since": freq.days_since_last_purchase,
                    "next_expected": freq.next_expected_purchase.isoformat()
                    if freq.next_expected_purchase
                    else None,
                    "confidence": freq.confidence,
                    "total_purchases": len(freq.purchase_history),
                },
            },
        }
        formatter.output(output_data, f"Frequency data for {item}")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@stats_app.command("compare")
def stats_compare(
    item: Annotated[str, typer.Argument(help="Item name to compare prices")],
) -> None:
    """Compare prices for an item across stores."""
    try:
        analytics = Analytics(data_store=get_data_store())
        comparison = analytics.price_comparison(item)

        if not comparison:
            formatter.warning(f"No price data for '{item}' to compare")
            return

        output_data = {
            "success": True,
            "data": {
                "comparison": comparison.model_dump(),
            },
        }
        formatter.output(output_data, f"Price comparison for {item}")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@stats_app.command("suggest")
def stats_suggest() -> None:
    """Get smart shopping suggestions."""
    try:
        analytics = Analytics(data_store=get_data_store())
        suggestions = analytics.get_suggestions()

        output_data = {
            "success": True,
            "data": {
                "suggestions": [s.model_dump() for s in suggestions],
            },
        }
        formatter.output(
            output_data,
            f"Found {len(suggestions)} suggestions" if suggestions else "No suggestions",
        )
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


# Out-of-stock subcommand group
oos_app = typer.Typer(help="Out-of-stock tracking")
app.add_typer(oos_app, name="out-of-stock")


@oos_app.command("report")
def oos_report(
    item: Annotated[str, typer.Argument(help="Item name that was out of stock")],
    store: Annotated[str, typer.Argument(help="Store where it was out of stock")],
    substitution: Annotated[
        str | None, typer.Option("--sub", "-s", help="What was bought instead")
    ] = None,
    reported_by: Annotated[
        str | None, typer.Option("--by", help="Who is reporting")
    ] = None,
) -> None:
    """Report an item as out of stock at a store."""
    try:
        analytics = Analytics(data_store=get_data_store())
        record = analytics.record_out_of_stock(
            item_name=item,
            store=store,
            substitution=substitution,
            reported_by=reported_by,
        )

        output_data = {
            "success": True,
            "message": f"Recorded {item} as out of stock at {store}",
            "data": {
                "record": record.model_dump(),
            },
        }
        formatter.output(output_data, output_data["message"])
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@oos_app.command("list")
def oos_list(
    item: Annotated[
        str | None, typer.Option("--item", "-i", help="Filter by item name")
    ] = None,
    store: Annotated[
        str | None, typer.Option("--store", "-s", help="Filter by store")
    ] = None,
) -> None:
    """List out-of-stock records."""
    try:
        ds = get_data_store()
        if item:
            records = ds.get_out_of_stock_for_item(item, store)
        else:
            records = ds.load_out_of_stock()
            if store:
                records = [r for r in records if r.store.lower() == store.lower()]

        output_data = {
            "success": True,
            "data": {
                "out_of_stock": [r.model_dump() for r in records],
            },
        }
        formatter.output(
            output_data,
            f"Found {len(records)} out-of-stock records",
        )
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
