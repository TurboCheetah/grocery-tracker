"""CLI entry point for Grocery Tracker."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .analytics import Analytics
from .config import ConfigManager
from .data_store import BackendType, DataStore, create_data_store
from .inventory_manager import InventoryManager
from .list_manager import DuplicateItemError, ItemNotFoundError, ListManager
from .models import InventoryLocation, ItemStatus, Priority, WasteReason
from .output_formatter import OutputFormatter
from .receipt_processor import ReceiptProcessor

app = typer.Typer(
    name="grocery",
    help="Intelligent grocery list and inventory management",
    no_args_is_help=True,
)

console = Console()

# Global state for formatter and config (set by callback)
formatter: OutputFormatter = OutputFormatter()
config: ConfigManager | None = None
data_store: DataStore | None = None
list_manager: ListManager | None = None
inventory_manager: InventoryManager | None = None


def get_config() -> ConfigManager:
    """Get or create ConfigManager instance."""
    global config
    if config is None:
        config = ConfigManager()
    return config


def get_data_store() -> DataStore:
    """Get or create DataStore instance using config values."""
    global data_store
    if data_store is None:
        cfg = get_config()
        backend = BackendType(cfg.data.backend)
        data_store = create_data_store(backend=backend, data_dir=cfg.data.storage_dir)  # type: ignore[assignment]
    return data_store  # type: ignore[return-value]


def get_list_manager() -> ListManager:
    """Get or create ListManager instance."""
    global list_manager
    if list_manager is None:
        list_manager = ListManager(get_data_store())
    return list_manager


def get_inventory_manager() -> InventoryManager:
    """Get or create InventoryManager instance."""
    global inventory_manager
    if inventory_manager is None:
        inventory_manager = InventoryManager(get_data_store())
    return inventory_manager


@app.callback()
def main(
    json_output: Annotated[
        bool, typer.Option("--json", help="Output as JSON for programmatic use")
    ] = False,
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="Data directory path")] = None,
) -> None:
    """Grocery Tracker CLI - Manage your grocery lists with intelligence."""
    global formatter, config, data_store, list_manager, inventory_manager

    formatter = OutputFormatter(json_mode=json_output)

    # Load config early
    config = ConfigManager()

    # CLI --data-dir overrides config, which overrides default
    effective_data_dir = data_dir if data_dir else config.data.storage_dir
    backend = BackendType(config.data.backend)

    data_store = create_data_store(backend=backend, data_dir=effective_data_dir)  # type: ignore[assignment]
    list_manager = ListManager(data_store)  # type: ignore[arg-type]
    inventory_manager = InventoryManager(data_store)  # type: ignore[arg-type]


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
        cfg = get_config()
        manager = get_list_manager()
        result = manager.add_item(
            name=item,
            quantity=quantity,
            store=store or cfg.defaults.store,
            category=category or cfg.defaults.category,
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
        cfg = get_config()
        effective_budget = budget if budget is not None else cfg.budget.monthly_limit
        analytics = Analytics(data_store=get_data_store())
        summary = analytics.spending_summary(period=period, budget_limit=effective_budget)

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


@stats_app.command("seasonal")
def stats_seasonal(
    item: Annotated[str | None, typer.Argument(help="Item name (omit when using --all)")] = None,
    all_items: Annotated[
        bool, typer.Option("--all", help="Show seasonal patterns for all items")
    ] = False,
) -> None:
    """View seasonal purchase patterns for an item or all items."""
    try:
        analytics = Analytics(data_store=get_data_store())
        if all_items:
            patterns = analytics.get_seasonal_patterns()
            output_data = {
                "success": True,
                "data": {
                    "seasonal_items": [p.model_dump() for p in patterns],
                    "total_items": len(patterns),
                },
            }
            formatter.output(
                output_data,
                (
                    f"Seasonal patterns for {len(patterns)} items"
                    if patterns
                    else "No seasonal patterns"
                ),
            )
            return

        if not item:
            formatter.error("Provide an item name or use --all")
            raise typer.Exit(code=1)

        pattern = analytics.get_seasonal_pattern(item)

        if not pattern:
            formatter.warning(f"No seasonal pattern data for '{item}'")
            return

        output_data = {
            "success": True,
            "data": {
                "seasonal": pattern.model_dump(),
            },
        }
        formatter.output(output_data, f"Seasonal pattern for {pattern.item_name}")
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


@stats_app.command("bulk")
def stats_bulk(
    lookback_days: Annotated[
        int, typer.Option("--days", "-d", help="Days of history to estimate usage")
    ] = 90,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max recommendations to return")] = 5,
    min_savings_pct: Annotated[
        float,
        typer.Option("--min-savings-pct", help="Minimum percent savings per unit"),
    ] = 5.0,
    min_savings_abs: Annotated[
        float,
        typer.Option("--min-savings", help="Minimum absolute savings per unit"),
    ] = 0.05,
) -> None:
    """Analyze bulk buying opportunities."""
    try:
        analytics = Analytics(data_store=get_data_store())
        recommendations = analytics.bulk_buying_analysis(
            lookback_days=lookback_days,
            min_savings_pct=min_savings_pct,
            min_savings_abs=min_savings_abs,
            limit=limit,
        )

        output_data = {
            "success": True,
            "data": {
                "bulk_buying": {
                    "lookback_days": lookback_days,
                    "recommendations": [r.model_dump() for r in recommendations],
                },
            },
        }

        message = (
            f"Found {len(recommendations)} bulk buying opportunities"
            if recommendations
            else "No bulk buying opportunities"
        )
        formatter.output(output_data, message)
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
    reported_by: Annotated[str | None, typer.Option("--by", help="Who is reporting")] = None,
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
    item: Annotated[str | None, typer.Option("--item", "-i", help="Filter by item name")] = None,
    store: Annotated[str | None, typer.Option("--store", "-s", help="Filter by store")] = None,
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


# --- Phase 3: Inventory subcommand group ---
inv_app = typer.Typer(help="Inventory management commands")
app.add_typer(inv_app, name="inventory")


@inv_app.command("add")
def inv_add(
    item: Annotated[str, typer.Argument(help="Item name")],
    quantity: Annotated[float, typer.Option("--quantity", "-q", help="Quantity")] = 1.0,
    unit: Annotated[str | None, typer.Option("--unit", "-u", help="Unit of measurement")] = None,
    category: Annotated[str | None, typer.Option("--category", "-c", help="Category")] = None,
    location: Annotated[
        InventoryLocation, typer.Option("--location", "-l", help="Storage location")
    ] = InventoryLocation.PANTRY,
    expiration: Annotated[
        str | None, typer.Option("--expires", help="Expiration date (YYYY-MM-DD)")
    ] = None,
    threshold: Annotated[float, typer.Option("--threshold", help="Low stock threshold")] = 1.0,
    added_by: Annotated[str | None, typer.Option("--by", help="Who is adding")] = None,
) -> None:
    """Add an item to household inventory."""
    try:
        from datetime import date as date_type

        exp_date = date_type.fromisoformat(expiration) if expiration else None

        mgr = get_inventory_manager()
        result = mgr.add_item(
            item_name=item,
            quantity=quantity,
            unit=unit,
            category=category or "Other",
            location=location,
            expiration_date=exp_date,
            low_stock_threshold=threshold,
            added_by=added_by,
        )

        output_data = {
            "success": True,
            "message": f"Added {item} to inventory ({location.value})",
            "data": {"inventory_item": result.model_dump()},
        }
        formatter.output(output_data, output_data["message"])
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@inv_app.command("remove")
def inv_remove(
    item_id: Annotated[str, typer.Argument(help="Item ID to remove")],
) -> None:
    """Remove an item from inventory."""
    try:
        mgr = get_inventory_manager()
        removed = mgr.remove_item(item_id)
        output_data = {
            "success": True,
            "message": f"Removed {removed.item_name} from inventory",
            "data": {"inventory_item": removed.model_dump()},
        }
        formatter.output(output_data, output_data["message"])
    except ValueError as e:
        formatter.error(str(e), error_code="ITEM_NOT_FOUND")
        raise typer.Exit(code=1)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@inv_app.command("list")
def inv_list(
    location: Annotated[
        InventoryLocation | None, typer.Option("--location", "-l", help="Filter by location")
    ] = None,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Filter by category")
    ] = None,
) -> None:
    """View household inventory."""
    try:
        mgr = get_inventory_manager()
        items = mgr.get_inventory(location=location, category=category)

        output_data = {
            "success": True,
            "data": {
                "inventory": [i.model_dump() for i in items],
                "count": len(items),
            },
        }
        formatter.output(output_data, f"{len(items)} items in inventory")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@inv_app.command("expiring")
def inv_expiring(
    days: Annotated[int, typer.Option("--days", "-d", help="Days to look ahead")] = 3,
) -> None:
    """View items expiring soon."""
    try:
        mgr = get_inventory_manager()
        items = mgr.get_expiring_soon(days=days)

        output_data = {
            "success": True,
            "data": {
                "expiring": [i.model_dump() for i in items],
                "count": len(items),
                "days": days,
            },
        }
        formatter.output(output_data, f"{len(items)} items expiring within {days} days")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@inv_app.command("low-stock")
def inv_low_stock() -> None:
    """View items that are low on stock."""
    try:
        mgr = get_inventory_manager()
        items = mgr.get_low_stock()

        output_data = {
            "success": True,
            "data": {
                "low_stock": [i.model_dump() for i in items],
                "count": len(items),
            },
        }
        formatter.output(output_data, f"{len(items)} items are low on stock")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@inv_app.command("use")
def inv_use(
    item_id: Annotated[str, typer.Argument(help="Item ID")],
    quantity: Annotated[float, typer.Option("--quantity", "-q", help="Amount to use")] = 1.0,
) -> None:
    """Use/consume inventory (reduce quantity)."""
    try:
        mgr = get_inventory_manager()
        updated = mgr.update_quantity(item_id, delta=-quantity)

        output_data = {
            "success": True,
            "message": f"Used {quantity} of {updated.item_name} (remaining: {updated.quantity})",
            "data": {"inventory_item": updated.model_dump()},
        }
        formatter.output(output_data, output_data["message"])
    except ValueError as e:
        formatter.error(str(e), error_code="ITEM_NOT_FOUND")
        raise typer.Exit(code=1)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


# --- Phase 3: Waste subcommand group ---
waste_app = typer.Typer(help="Waste tracking commands")
app.add_typer(waste_app, name="waste")


@waste_app.command("log")
def waste_log(
    item: Annotated[str, typer.Argument(help="Item name that was wasted")],
    quantity: Annotated[float, typer.Option("--quantity", "-q", help="Amount wasted")] = 1.0,
    unit: Annotated[str | None, typer.Option("--unit", "-u", help="Unit")] = None,
    reason: Annotated[
        WasteReason, typer.Option("--reason", "-r", help="Reason for waste")
    ] = WasteReason.OTHER,
    cost: Annotated[float | None, typer.Option("--cost", help="Estimated cost")] = None,
    logged_by: Annotated[str | None, typer.Option("--by", help="Who is logging")] = None,
) -> None:
    """Log a wasted item."""
    try:
        analytics = Analytics(data_store=get_data_store())
        record = analytics.log_waste(
            item_name=item,
            quantity=quantity,
            unit=unit,
            reason=reason,
            estimated_cost=cost,
            logged_by=logged_by,
        )

        output_data = {
            "success": True,
            "message": f"Logged waste: {item} ({reason.value})",
            "data": {"record": record.model_dump()},
        }
        formatter.output(output_data, output_data["message"])
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@waste_app.command("list")
def waste_list(
    item: Annotated[str | None, typer.Option("--item", "-i", help="Filter by item")] = None,
    reason: Annotated[
        WasteReason | None, typer.Option("--reason", "-r", help="Filter by reason")
    ] = None,
) -> None:
    """List waste records."""
    try:
        ds = get_data_store()
        records = ds.load_waste_log()

        if item:
            records = [r for r in records if r.item_name.lower() == item.lower()]
        if reason:
            records = [r for r in records if r.reason == reason]

        output_data = {
            "success": True,
            "data": {
                "waste_log": [r.model_dump() for r in records],
                "count": len(records),
            },
        }
        formatter.output(output_data, f"{len(records)} waste records")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@waste_app.command("summary")
def waste_summary(
    period: Annotated[
        str, typer.Option("--period", "-p", help="Period: weekly, monthly, yearly")
    ] = "monthly",
) -> None:
    """View waste summary and insights."""
    try:
        analytics = Analytics(data_store=get_data_store())
        summary = analytics.waste_summary(period=period)
        insights = analytics.waste_insights()

        output_data = {
            "success": True,
            "data": {
                "waste_summary": summary,
                "insights": insights,
            },
        }
        formatter.output(output_data, f"Waste summary ({period})")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


# --- Phase 3: Budget subcommand group ---
budget_app = typer.Typer(help="Budget tracking commands")
app.add_typer(budget_app, name="budget")


@budget_app.command("set")
def budget_set(
    limit: Annotated[float, typer.Argument(help="Monthly budget limit")],
    month: Annotated[str | None, typer.Option("--month", help="Month (YYYY-MM)")] = None,
) -> None:
    """Set monthly budget."""
    try:
        analytics = Analytics(data_store=get_data_store())
        budget = analytics.set_budget(monthly_limit=limit, month=month)

        output_data = {
            "success": True,
            "message": f"Budget set: ${limit:.2f}/month for {budget.month}",
            "data": {"budget": budget.model_dump()},
        }
        formatter.output(output_data, output_data["message"])
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@budget_app.command("status")
def budget_status(
    month: Annotated[str | None, typer.Option("--month", help="Month (YYYY-MM)")] = None,
) -> None:
    """View budget status."""
    try:
        analytics = Analytics(data_store=get_data_store())
        budget = analytics.get_budget_status(month=month)

        if budget is None:
            formatter.warning("No budget set for this month")
            return

        output_data = {
            "success": True,
            "data": {"budget_status": budget.model_dump()},
        }
        formatter.output(output_data, f"Budget status for {budget.month}")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


# --- Phase 3: Preferences subcommand group ---
prefs_app = typer.Typer(help="User preference commands")
app.add_typer(prefs_app, name="preferences")


@prefs_app.command("view")
def prefs_view(
    user: Annotated[str, typer.Argument(help="Username")],
) -> None:
    """View user preferences."""
    try:
        ds = get_data_store()
        prefs = ds.get_user_preferences(user)

        if prefs is None:
            formatter.warning(f"No preferences found for '{user}'")
            return

        output_data = {
            "success": True,
            "data": {"preferences": prefs.model_dump()},
        }
        formatter.output(output_data, f"Preferences for {user}")
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


@prefs_app.command("set")
def prefs_set(
    user: Annotated[str, typer.Argument(help="Username")],
    brand: Annotated[
        list[str] | None, typer.Option("--brand", help="Brand preference (item:brand)")
    ] = None,
    dietary: Annotated[
        list[str] | None, typer.Option("--dietary", help="Dietary restriction")
    ] = None,
    allergen: Annotated[list[str] | None, typer.Option("--allergen", help="Allergen")] = None,
    favorite: Annotated[list[str] | None, typer.Option("--favorite", help="Favorite item")] = None,
) -> None:
    """Set user preferences."""
    try:
        from .models import UserPreferences

        ds = get_data_store()
        existing = ds.get_user_preferences(user)

        if existing is None:
            existing = UserPreferences(user=user)

        if brand:
            for b in brand:
                if ":" in b:
                    item, brand_name = b.split(":", 1)
                    existing.brand_preferences[item.strip()] = brand_name.strip()

        if dietary:
            for d in dietary:
                if d not in existing.dietary_restrictions:
                    existing.dietary_restrictions.append(d)

        if allergen:
            for a in allergen:
                if a not in existing.allergens:
                    existing.allergens.append(a)

        if favorite:
            for f in favorite:
                if f not in existing.favorite_items:
                    existing.favorite_items.append(f)

        ds.save_user_preferences(existing)

        output_data = {
            "success": True,
            "message": f"Updated preferences for {user}",
            "data": {"preferences": existing.model_dump()},
        }
        formatter.output(output_data, output_data["message"])
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
