# Grocery Tracker

Intelligent grocery list and inventory management for households.

## Features

- **Grocery List Management**: Add, remove, update, and mark items as bought
- **Receipt Processing**: Process receipt data to reconcile with your shopping list
- **Price Tracking**: Track price history across stores over time
- **Multi-user Support**: Track who added what and personal preferences
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

### Command Shape (Important)

`grocery` has global options: `--json` and `--data-dir`.

```bash
# Example
grocery --json --data-dir ./data list
```

Some features are nested subcommands:

```bash
grocery price history "Milk"
grocery receipt process --file receipt.json
```

`stats` works in two ways:

```bash
# Base command: spending summary
grocery stats --period monthly

# Subcommands: deeper analytics
grocery stats suggest
grocery stats compare "Milk"
```

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
grocery receipt process --data '{"store_name": "Giant", "transaction_date": "2024-01-15", "line_items": [{"item_name": "Milk", "quantity": 1, "unit_price": 4.99, "total_price": 4.99}], "subtotal": 4.99, "total": 5.29}'
```

### Price History

```bash
grocery price history "Milk"
grocery price history "Milk" --store Giant
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
