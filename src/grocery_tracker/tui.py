"""Terminal UI for Grocery Tracker."""

from __future__ import annotations

from datetime import date
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from .inventory_manager import InventoryManager
from .list_manager import DuplicateItemError, ItemNotFoundError, ListManager
from .models import InventoryItem, InventoryLocation, ItemStatus, Priority


class ListItemFormScreen(ModalScreen[dict[str, Any] | None]):
    """Modal dialog to add or edit grocery list items."""

    DEFAULT_CSS = """
    ListItemFormScreen {
        align: center middle;
    }

    #list-item-form-dialog {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }

    #list-item-form-actions {
        align-horizontal: right;
        height: auto;
        margin-top: 1;
    }

    .field-label {
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, mode: str, defaults: dict[str, Any] | None = None):
        super().__init__()
        self.mode = mode
        self.defaults = defaults or {}

    def compose(self) -> ComposeResult:
        is_edit = self.mode == "edit"
        title = "Edit Grocery List Item" if is_edit else "Add Grocery List Item"
        submit = "Save" if is_edit else "Add"

        with Vertical(id="list-item-form-dialog"):
            yield Label(title, classes="field-label")
            yield Label("Name", classes="field-label")
            yield Input(value=self._value("name"), placeholder="Milk", id="name")
            yield Label("Quantity", classes="field-label")
            yield Input(value=self._value("quantity", "1"), id="quantity")
            yield Label("Store (optional)", classes="field-label")
            yield Input(value=self._value("store"), placeholder="Safeway", id="store")
            yield Label("Category", classes="field-label")
            yield Input(value=self._value("category"), placeholder="Dairy", id="category")
            yield Label("Unit (optional)", classes="field-label")
            yield Input(value=self._value("unit"), placeholder="count", id="unit")
            yield Label("Brand (optional)", classes="field-label")
            yield Input(
                value=self._value("brand_preference"), placeholder="Store brand", id="brand"
            )
            yield Label("Estimated Price (optional)", classes="field-label")
            yield Input(value=self._value("estimated_price"), placeholder="4.99", id="price")
            yield Label("Priority: high | medium | low", classes="field-label")
            yield Input(value=self._value("priority", Priority.MEDIUM.value), id="priority")
            yield Label("Status: to_buy | bought | still_needed", classes="field-label")
            yield Input(value=self._value("status", ItemStatus.TO_BUY.value), id="status")
            yield Label("Notes (optional)", classes="field-label")
            yield Input(value=self._value("notes"), placeholder="Any extra detail", id="notes")
            with Horizontal(id="list-item-form-actions"):
                yield Button("Cancel", id="cancel")
                yield Button(submit, id="submit", variant="primary")

    def _value(self, key: str, fallback: str = "") -> str:
        value = self.defaults.get(key)
        if value is None:
            return fallback
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        if event.button.id != "submit":
            return

        name = self.query_one("#name", Input).value.strip()
        quantity_raw = self.query_one("#quantity", Input).value.strip() or "1"
        store_raw = self.query_one("#store", Input).value.strip()
        category_raw = self.query_one("#category", Input).value.strip()
        unit_raw = self.query_one("#unit", Input).value.strip()
        brand_raw = self.query_one("#brand", Input).value.strip()
        price_raw = self.query_one("#price", Input).value.strip()
        priority_raw = (
            self.query_one("#priority", Input).value.strip().lower() or Priority.MEDIUM.value
        )
        status_raw = (
            self.query_one("#status", Input).value.strip().lower() or ItemStatus.TO_BUY.value
        )
        notes_raw = self.query_one("#notes", Input).value.strip()

        if not name:
            self.app.bell()
            return

        try:
            quantity = float(quantity_raw)
            price = float(price_raw) if price_raw else None
            priority = Priority(priority_raw)
            status = ItemStatus(status_raw)
        except ValueError:
            self.app.bell()
            return

        self.dismiss(
            {
                "name": name,
                "quantity": quantity,
                "store": store_raw or None,
                "category": category_raw or "Other",
                "unit": unit_raw or None,
                "brand": brand_raw or None,
                "price": price,
                "priority": priority,
                "status": status,
                "notes": notes_raw or None,
            }
        )


class InventoryItemFormScreen(ModalScreen[dict[str, Any] | None]):
    """Modal dialog to add or edit inventory items."""

    DEFAULT_CSS = """
    InventoryItemFormScreen {
        align: center middle;
    }

    #inventory-item-form-dialog {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    #inventory-item-form-actions {
        align-horizontal: right;
        height: auto;
        margin-top: 1;
    }

    .field-label {
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, mode: str, defaults: dict[str, Any] | None = None):
        super().__init__()
        self.mode = mode
        self.defaults = defaults or {}

    def compose(self) -> ComposeResult:
        is_edit = self.mode == "edit"
        title = "Edit Inventory Item" if is_edit else "Add Inventory Item"
        submit = "Save" if is_edit else "Add"

        with Vertical(id="inventory-item-form-dialog"):
            yield Label(title, classes="field-label")
            yield Label("Name", classes="field-label")
            yield Input(value=self._value("item_name"), placeholder="Eggs", id="name")
            yield Label("Quantity", classes="field-label")
            yield Input(value=self._value("quantity", "1"), id="quantity")
            yield Label("Unit (optional)", classes="field-label")
            yield Input(value=self._value("unit"), placeholder="count", id="unit")
            yield Label("Category", classes="field-label")
            yield Input(value=self._value("category", "Other"), id="category")
            yield Label("Location: pantry | fridge | freezer", classes="field-label")
            yield Input(
                value=self._value("location", InventoryLocation.PANTRY.value), id="location"
            )
            yield Label("Low-stock threshold", classes="field-label")
            yield Input(value=self._value("low_stock_threshold", "1"), id="threshold")
            yield Label("Expiration (YYYY-MM-DD, optional)", classes="field-label")
            yield Input(
                value=self._value("expiration_date"), placeholder="2026-03-01", id="expiration"
            )
            with Horizontal(id="inventory-item-form-actions"):
                yield Button("Cancel", id="cancel")
                yield Button(submit, id="submit", variant="primary")

    def _value(self, key: str, fallback: str = "") -> str:
        value = self.defaults.get(key)
        if value is None:
            return fallback
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        if event.button.id != "submit":
            return

        name = self.query_one("#name", Input).value.strip()
        quantity_raw = self.query_one("#quantity", Input).value.strip() or "1"
        unit_raw = self.query_one("#unit", Input).value.strip()
        category_raw = self.query_one("#category", Input).value.strip() or "Other"
        location_raw = self.query_one("#location", Input).value.strip().lower()
        threshold_raw = self.query_one("#threshold", Input).value.strip() or "1"
        expiration_raw = self.query_one("#expiration", Input).value.strip()

        if not name:
            self.app.bell()
            return

        try:
            quantity = float(quantity_raw)
            location = InventoryLocation(location_raw)
            threshold = float(threshold_raw)
            expiration = date.fromisoformat(expiration_raw) if expiration_raw else None
        except ValueError:
            self.app.bell()
            return

        self.dismiss(
            {
                "item_name": name,
                "quantity": quantity,
                "unit": unit_raw or None,
                "category": category_raw,
                "location": location,
                "low_stock_threshold": threshold,
                "expiration_date": expiration,
            }
        )


class GroceryTrackerTUI(App[None]):
    """Interactive terminal UI for grocery and inventory workflows."""

    TITLE = "Grocery Tracker"
    SUB_TITLE = "Terminal Interface"

    DEFAULT_CSS = """
    #status {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $boost;
        color: $text;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("a", "add_to_list", "Add List Item"),
        Binding("i", "add_to_inventory", "Add Inventory"),
        Binding("e", "edit_selected", "Edit Selected"),
        Binding("b", "mark_bought", "Mark Bought"),
        Binding("x", "remove_selected", "Remove Selected"),
        Binding("u", "use_inventory_item", "Use 1"),
        Binding("s", "show_shopping", "Shopping Tab"),
        Binding("v", "show_inventory", "Inventory Tab"),
    ]

    def __init__(self, list_manager: ListManager, inventory_manager: InventoryManager):
        super().__init__()
        self.list_manager = list_manager
        self.inventory_manager = inventory_manager
        self._shopping_ids: list[str] = []
        self._inventory_ids: list[str] = []
        self._shopping_items: dict[str, dict[str, Any]] = {}
        self._inventory_items: dict[str, InventoryItem] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="shopping"):
            with TabPane("Shopping List", id="shopping"):
                yield DataTable(id="shopping-table")
            with TabPane("Inventory", id="inventory"):
                yield DataTable(id="inventory-table")
        yield Static(
            "a:add list  i:add inventory  e:edit  b:bought  x:remove  u:use one  r:refresh  q:quit",
            id="status",
        )
        yield Footer()

    def on_mount(self) -> None:
        shopping_table = self.query_one("#shopping-table", DataTable)
        shopping_table.cursor_type = "row"
        shopping_table.add_columns("Item", "Qty", "Store", "Category", "Status")

        inventory_table = self.query_one("#inventory-table", DataTable)
        inventory_table.cursor_type = "row"
        inventory_table.add_columns("Item", "Qty", "Unit", "Location", "Expires")

        self.action_refresh()

    def action_refresh(self) -> None:
        try:
            self._refresh_shopping_table()
            self._refresh_inventory_table()
            self._set_status("Refreshed grocery list and inventory")
        except Exception as exc:
            self._set_status(f"Refresh failed: {exc}")

    def action_add_to_list(self) -> None:
        self.push_screen(ListItemFormScreen(mode="add"), self._handle_add_list)

    def action_add_to_inventory(self) -> None:
        self.push_screen(InventoryItemFormScreen(mode="add"), self._handle_add_inventory)

    def action_edit_selected(self) -> None:
        active_tab = self._active_tab()
        item_id = self._selected_id(active_tab)

        if item_id is None:
            self._set_status("No item selected")
            return

        if active_tab == "shopping":
            item = self._shopping_items.get(item_id)
            if item is None:
                self._set_status("Selected shopping item is unavailable")
                return

            self.push_screen(
                ListItemFormScreen(mode="edit", defaults=item),
                lambda payload, selected_id=item_id: self._handle_edit_list(selected_id, payload),
            )
            return

        item = self._inventory_items.get(item_id)
        if item is None:
            self._set_status("Selected inventory item is unavailable")
            return

        self.push_screen(
            InventoryItemFormScreen(mode="edit", defaults=self._inventory_defaults(item)),
            lambda payload, selected_id=item_id: self._handle_edit_inventory(selected_id, payload),
        )

    def action_mark_bought(self) -> None:
        if self._active_tab() != "shopping":
            self._set_status("Switch to Shopping List tab to mark items bought")
            return

        item_id = self._selected_id("shopping")
        if item_id is None:
            self._set_status("No shopping list item selected")
            return

        try:
            result = self.list_manager.mark_bought(item_id)
            self.action_refresh()
            self._set_status(result["message"])
        except ItemNotFoundError as exc:
            self._set_status(str(exc))
        except Exception as exc:
            self._set_status(f"Mark bought failed: {exc}")

    def action_remove_selected(self) -> None:
        active_tab = self._active_tab()
        item_id = self._selected_id(active_tab)
        if item_id is None:
            self._set_status("No item selected")
            return

        try:
            if active_tab == "shopping":
                result = self.list_manager.remove_item(item_id)
                self._set_status(result["message"])
            else:
                removed = self.inventory_manager.remove_item(item_id)
                self._set_status(f"Removed {removed.item_name} from inventory")
            self.action_refresh()
        except Exception as exc:
            self._set_status(f"Remove failed: {exc}")

    def action_use_inventory_item(self) -> None:
        if self._active_tab() != "inventory":
            self._set_status("Switch to Inventory tab to consume items")
            return

        item_id = self._selected_id("inventory")
        if item_id is None:
            self._set_status("No inventory item selected")
            return

        try:
            updated = self.inventory_manager.update_quantity(item_id, delta=-1.0)
            self.action_refresh()
            self._set_status(f"Used 1 of {updated.item_name} (remaining: {updated.quantity})")
        except Exception as exc:
            self._set_status(f"Use failed: {exc}")

    def action_show_shopping(self) -> None:
        self.query_one(TabbedContent).active = "shopping"

    def action_show_inventory(self) -> None:
        self.query_one(TabbedContent).active = "inventory"

    def _refresh_shopping_table(self) -> None:
        table = self.query_one("#shopping-table", DataTable)
        table.clear(columns=False)
        self._shopping_ids = []
        self._shopping_items = {}

        result = self.list_manager.get_list()
        items = result["data"]["list"]["items"]

        for item in items:
            item_id = str(item["id"])
            self._shopping_ids.append(item_id)
            self._shopping_items[item_id] = item
            table.add_row(
                item["name"],
                str(item.get("quantity", 1)),
                item.get("store") or "-",
                item.get("category") or "Other",
                item.get("status") or "to_buy",
                key=item_id,
            )

        if self._shopping_ids:
            table.move_cursor(row=0, column=0)

    def _refresh_inventory_table(self) -> None:
        table = self.query_one("#inventory-table", DataTable)
        table.clear(columns=False)
        self._inventory_ids = []
        self._inventory_items = {}

        items = self.inventory_manager.get_inventory()

        for item in items:
            item_id = str(item.id)
            self._inventory_ids.append(item_id)
            self._inventory_items[item_id] = item
            table.add_row(
                item.item_name,
                str(item.quantity),
                item.unit or "-",
                item.location.value,
                item.expiration_date.isoformat() if item.expiration_date else "-",
                key=item_id,
            )

        if self._inventory_ids:
            table.move_cursor(row=0, column=0)

    def _handle_add_list(self, payload: dict[str, Any] | None) -> None:
        if payload is None:
            self._set_status("Add grocery item canceled")
            return

        try:
            result = self.list_manager.add_item(
                name=payload["name"],
                quantity=payload["quantity"],
                store=payload["store"],
                category=payload["category"],
                unit=payload["unit"],
                brand_preference=payload["brand"],
                estimated_price=payload["price"],
                priority=payload["priority"],
                notes=payload["notes"],
            )
            self.action_refresh()
            self._set_status(result["message"])
        except DuplicateItemError as exc:
            self._set_status(str(exc))
        except Exception as exc:
            self._set_status(f"Add failed: {exc}")

    def _handle_edit_list(self, item_id: str, payload: dict[str, Any] | None) -> None:
        if payload is None:
            self._set_status("Edit canceled")
            return

        try:
            result = self.list_manager.update_item(
                item_id=item_id,
                name=payload["name"],
                quantity=payload["quantity"],
                store=payload["store"],
                category=payload["category"],
                unit=payload["unit"],
                brand_preference=payload["brand"],
                estimated_price=payload["price"],
                priority=payload["priority"],
                notes=payload["notes"],
                status=payload["status"],
                treat_none_as_unset=False,
            )
            self.action_refresh()
            self._set_status(result["message"])
        except ItemNotFoundError as exc:
            self._set_status(str(exc))
        except Exception as exc:
            self._set_status(f"Edit failed: {exc}")

    def _handle_add_inventory(self, payload: dict[str, Any] | None) -> None:
        if payload is None:
            self._set_status("Add inventory item canceled")
            return

        try:
            added = self.inventory_manager.add_item(
                item_name=payload["item_name"],
                quantity=payload["quantity"],
                unit=payload["unit"],
                category=payload["category"],
                location=payload["location"],
                expiration_date=payload["expiration_date"],
                low_stock_threshold=payload["low_stock_threshold"],
            )
            self.action_refresh()
            self._set_status(f"Added {added.item_name} to inventory")
        except Exception as exc:
            self._set_status(f"Add inventory failed: {exc}")

    def _handle_edit_inventory(self, item_id: str, payload: dict[str, Any] | None) -> None:
        if payload is None:
            self._set_status("Edit canceled")
            return

        try:
            updated = self.inventory_manager.update_item(
                item_id=item_id,
                item_name=payload["item_name"],
                quantity=payload["quantity"],
                unit=payload["unit"],
                category=payload["category"],
                location=payload["location"],
                expiration_date=payload["expiration_date"],
                low_stock_threshold=payload["low_stock_threshold"],
                treat_none_as_unset=False,
            )
            self.action_refresh()
            self._set_status(f"Updated {updated.item_name}")
        except ValueError as exc:
            self._set_status(str(exc))
        except Exception as exc:
            self._set_status(f"Edit inventory failed: {exc}")

    def _inventory_defaults(self, item: InventoryItem) -> dict[str, Any]:
        return {
            "item_name": item.item_name,
            "quantity": item.quantity,
            "unit": item.unit,
            "category": item.category,
            "location": item.location,
            "low_stock_threshold": item.low_stock_threshold,
            "expiration_date": item.expiration_date.isoformat() if item.expiration_date else "",
        }

    def _selected_id(self, tab: str) -> str | None:
        if tab == "shopping":
            table = self.query_one("#shopping-table", DataTable)
            row = table.cursor_row
            if row is None or row < 0 or row >= len(self._shopping_ids):
                return None
            return self._shopping_ids[row]

        table = self.query_one("#inventory-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._inventory_ids):
            return None
        return self._inventory_ids[row]

    def _active_tab(self) -> str:
        tabbed_content = self.query_one(TabbedContent)
        return tabbed_content.active or "shopping"

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)
