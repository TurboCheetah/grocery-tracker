# Grocery Tracker

Intelligent grocery list and inventory management for households.

## Features

- **Grocery List Management**: Add, remove, update, and mark items as bought
- **Receipt Processing**: Process receipt data to reconcile with your shopping list
- **Price Tracking**: Track price history across stores over time
- **Multi-user Support**: Track who added what and personal preferences
- **Deals & Savings**: Track coupons/sales and savings over time
- **JSON Output**: Programmatic access via `--json` flag for LLM integration

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/grocery-tracker.git
cd grocery-tracker

# Install with uv
uv sync --all-extras
```

## Usage

### Add Items

```bash
# Basic
grocery add "Milk"

# With options
grocery add "Organic Milk" -q 2 -s Giant -c Dairy --brand Horizon --price 5.99

# JSON output for scripts
grocery --json add "Eggs" -q 12
```

### View List

```bash
# View all items
grocery list

# Filter by store
grocery list --store Giant

# Group by category
grocery list --by-category

# JSON output
grocery --json list
```

### Mark Items as Bought

```bash
grocery bought <item-id>
grocery bought <item-id> --price 4.99
```

### Process Receipts

```bash
grocery receipt process --data '{"store_name": "Giant", "transaction_date": "2024-01-15", "line_items": [{"item_name": "Milk", "quantity": 1, "unit_price": 4.99, "total_price": 4.99, "category": "Dairy & Eggs"}], "subtotal": 4.99, "total": 5.29}'
```

### Price History

```bash
grocery price history "Milk"
grocery price history "Milk" --store Giant
```

### Deals (Coupons/Sales)

```bash
# Add a sale
grocery deals add "Eggs" --store Giant --type sale --regular-price 3.99 --deal-price 2.99 --start 2026-02-01 --end 2026-02-07

# Add a coupon
grocery deals add "Cereal" --store Giant --type coupon --discount 1.00 --code SAVE1

# List active deals
grocery deals list

# List all deals
grocery deals list --status all

# Redeem a deal (logs savings)
grocery deals redeem <deal-id> --quantity 2
```

### Savings

```bash
# Log savings directly
grocery savings log "Milk" --store Giant --amount 1.50 --type coupon

# Log savings based on regular vs paid price
grocery savings log "Eggs" --regular-price 3.99 --paid-price 2.99 --quantity 2

# List savings records
grocery savings list

# Summary by period
grocery savings summary --period monthly
```

## Configuration

Copy `config.toml.example` to `~/.config/grocery-tracker/config.toml` and customize:

```toml
[defaults]
store = "Giant"
category = "Other"

[budget]
monthly_limit = 500.00
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linter
uv run ruff check src/
```

## License

MIT
