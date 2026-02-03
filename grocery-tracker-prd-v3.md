# Grocery Tracker — Product Requirements Document

**Version**: 1.0  
**Date**: January 26, 2026  
**Author**: Francisco  
**Status**: Draft for Review

---

## Executive Summary

A comprehensive grocery tracking and household inventory management system designed for shared use via Clawdbot integration in Telegram/Signal group chats. The system combines simple list management with sophisticated analytics including price tracking, purchase frequency analysis, spending patterns, and multi-store intelligence.

### Core Value Propositions

1. **Effortless list management** — Natural language item addition via chat interface
2. **Financial intelligence** — Price tracking, spending analytics, budget alerts
3. **Purchase optimization** — Frequency analysis, store comparison, bulk buying recommendations
4. **Household coordination** — Shared preferences, dietary tracking, collaborative shopping
5. **Receipt automation** — OCR-powered receipt processing with minimal manual input

---

## Implementation Status

**Last updated**: February 3, 2026  

- Phase 2 — Seasonal patterns (Purchase Frequency Analysis): Implemented (analytics computation, `stats seasonal` CLI for single/all items, seasonal suggestions, Rich/JSON output, tests)

---

## Technical Architecture

### Technology Stack: **Python with uv**

**Rationale for Python:**
- Superior libraries for data processing and analytics (Pydantic, datetime)
- Francisco's existing expertise and professional experience
- Rapid development and iteration capabilities
- Excellent for data-heavy operations (price tracking, frequency analysis)
- Strong support for JSON data persistence
- Modern tooling with `uv` for fast dependency management

**Package Manager: uv**
- 10-100x faster than pip
- Better dependency resolution
- Built-in virtual environment management
- Modern Python workflow

**Key Libraries:**
- `rich>=13.7.0` — Beautiful terminal UI for human interaction
- `typer>=0.12.0` — CLI framework with excellent UX
- `pydantic>=2.5.0` — Data validation and parsing
- `python-dateutil>=2.8.2` — Date/time handling
- `pytest>=8.0.0` — Testing framework (required)
- `pytest-cov>=4.1.0` — Coverage reporting

**NOT INCLUDED:**
- ~~anthropic~~ — Receipt extraction handled at skill layer
- ~~pytesseract/opencv~~ — No traditional OCR needed

### Deployment Model

**Application Type**: CLI tool invoked via Claude agent skill  
**Interface**: Group chat (Telegram/Signal) via Clawdbot mentions  
**Data Storage**: Local filesystem (JSON initially, SQLite migration planned)  
**Execution Context**: Runs on server where Clawdbot is hosted

### Configuration Management

**Configuration Format: TOML** (Python best practice)

**pyproject.toml (Project metadata + config):**
```toml
[project]
name = "grocery-tracker"
version = "0.1.0"
description = "Intelligent grocery list and inventory management"
authors = [{name = "Francisco", email = "francisco@example.com"}]
requires-python = ">=3.12"
dependencies = [
    "rich>=13.7.0",
    "typer>=0.12.0",
    "pydantic>=2.5.0",
    "python-dateutil>=2.8.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.1.0",  # Linting
]

[project.scripts]
grocery = "grocery_tracker.main:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = [
    "--verbose",
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=85",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**config.toml (User configuration):**
```toml
# ~/.config/grocery-tracker/config.toml
# or ./config.toml in project directory

[data]
storage_dir = "~/grocery-tracker/data"
backup_enabled = true
backup_interval_days = 7

[defaults]
store = "Giant"
category = "Other"

[budget]
monthly_limit = 500.00
alert_threshold = 0.9  # Alert at 90% of budget

[stores]
# Store configurations
[stores.giant]
name = "Giant Food"
typical_categories = ["Produce", "Dairy", "Meat", "Bakery"]

[stores.traderjoes]
name = "Trader Joe's"
typical_categories = ["Produce", "Frozen", "Snacks"]

[users.francisco]
dietary_restrictions = []
favorite_stores = ["Giant", "Trader Joe's"]

[users.loki]
dietary_restrictions = ["vegetarian"]
favorite_stores = ["Whole Foods", "Trader Joe's"]
```

**Loading Configuration (Python):**
```python
# src/config.py
from pathlib import Path
from typing import Any
import tomllib  # Built-in Python 3.11+
from dataclasses import dataclass

@dataclass
class DataConfig:
    storage_dir: Path
    backup_enabled: bool = True
    backup_interval_days: int = 7

@dataclass
class DefaultsConfig:
    store: str = "Giant"
    category: str = "Other"

@dataclass
class BudgetConfig:
    monthly_limit: float = 500.0
    alert_threshold: float = 0.9

@dataclass
class Config:
    data: DataConfig
    defaults: DefaultsConfig
    budget: BudgetConfig
    stores: dict[str, Any]
    users: dict[str, Any]

class ConfigManager:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or self._find_config()
        self.config = self._load_config()
    
    def _find_config(self) -> Path:
        """Find config file in standard locations"""
        locations = [
            Path.cwd() / "config.toml",
            Path.home() / ".config" / "grocery-tracker" / "config.toml",
            Path.home() / ".grocery-tracker" / "config.toml",
        ]
        
        for loc in locations:
            if loc.exists():
                return loc
        
        # Return default location if none found
        return Path.home() / ".config" / "grocery-tracker" / "config.toml"
    
    def _load_config(self) -> Config:
        """Load configuration from TOML file"""
        if not self.config_path.exists():
            return self._default_config()
        
        with open(self.config_path, 'rb') as f:
            data = tomllib.load(f)
        
        return Config(
            data=DataConfig(
                storage_dir=Path(data.get('data', {}).get('storage_dir', '~/grocery-tracker/data')).expanduser(),
                backup_enabled=data.get('data', {}).get('backup_enabled', True),
                backup_interval_days=data.get('data', {}).get('backup_interval_days', 7),
            ),
            defaults=DefaultsConfig(
                store=data.get('defaults', {}).get('store', 'Giant'),
                category=data.get('defaults', {}).get('category', 'Other'),
            ),
            budget=BudgetConfig(
                monthly_limit=data.get('budget', {}).get('monthly_limit', 500.0),
                alert_threshold=data.get('budget', {}).get('alert_threshold', 0.9),
            ),
            stores=data.get('stores', {}),
            users=data.get('users', {}),
        )
    
    def _default_config(self) -> Config:
        """Return default configuration"""
        return Config(
            data=DataConfig(
                storage_dir=Path.home() / "grocery-tracker" / "data"
            ),
            defaults=DefaultsConfig(),
            budget=BudgetConfig(),
            stores={},
            users={},
        )
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get config value by dot-notation path"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if hasattr(value, key):
                value = getattr(value, key)
            elif isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        
        return value if value is not None else default

# Usage
config = ConfigManager()
storage_dir = config.data.storage_dir
default_store = config.defaults.store
monthly_budget = config.budget.monthly_limit
```

---

## User Stories & Personas

### Primary Users

**Francisco** — ASD1, tech-savvy, runs Gentoo, professional fit specialist, detail-oriented data tracker  
**Loki** — Household member, grocery co-manager, shared shopping responsibilities

### User Stories

#### List Management
- "Add bananas to the grocery list" → System adds item with quantity prompt
- "What's on the grocery list?" → System shows categorized, store-organized view
- "Remove milk from list" → System removes item and confirms
- "Mark eggs as bought" → System moves to bought section, prompts for receipt

#### Receipt Processing
- Upload receipt photo → System extracts items, prices, store, date
- "I bought milk, eggs, bread for $15" → System parses text and updates
- "What did I forget to buy?" → System compares receipt to list, shows remaining items

#### Intelligence & Analytics
- "When do we usually buy milk?" → "Every 5 days on average, last purchased 4 days ago"
- "How much do we spend on groceries?" → "$450/month average over last 3 months"
- "Where's milk cheapest?" → "Trader Joe's: $3.49, Giant: $3.99, difference: $0.50"
- "Suggest what to buy" → Proactive recommendations based on frequency

#### Shared Household
- "What brand milk does Loki prefer?" → "Horizon Organic"
- "What are Francisco's dietary restrictions?" → Shows saved preferences
- "Who bought groceries last?" → Shows purchase attribution from last receipt

---

## Core Features

### Phase 1: MVP (Must-Have)

#### 1.1 Basic List Management
- **Add items** with natural language parsing
- **Remove items** from list
- **View list** in multiple formats (full markdown, channel-optimized, text-only)
- **Mark as bought** with partial purchase support
- **Duplicate detection** with user confirmation flow

**Data Model (Item):**
```json
{
  "id": "uuid",
  "name": "string",
  "quantity": "number | string",
  "unit": "string | null",
  "category": "string",
  "store": "string",
  "aisle": "string | null",
  "brand_preference": "string | null",
  "estimated_price": "number | null",
  "priority": "high | medium | low",
  "added_by": "Francisco | Loki",
  "added_at": "ISO8601 timestamp",
  "notes": "string | null"
}
```

#### 1.2 Store & Category Organization
- **Multi-store tracking** — Items tagged with preferred store
- **Category assignment** — Auto-categorize or manual override
- **Aisle mapping** — Optional aisle numbers for shopping route optimization
- **Store prompt on add** — "Which store? 1) Giant 2) Trader Joe's 3) Whole Foods"

**Categories (Suggested):**
- Produce
- Dairy & Eggs
- Meat & Seafood
- Bakery
- Pantry & Canned Goods
- Frozen Foods
- Beverages
- Snacks
- Health & Beauty
- Household Supplies
- Other

#### 1.3 Receipt Processing (OCR)
- **Image upload** → Extract via Tesseract OCR
- **Text parsing** → Manual fallback if photo unavailable
- **Data extraction:**
  - Store name
  - Transaction date & time
  - Line items (name, quantity, individual price)
  - Subtotal, tax, total
  - Payment method (optional)
- **List reconciliation** → Auto-detect what was bought vs still needed
- **User confirmation** → Review extracted data before saving

**Data Model (Receipt):**
```json
{
  "id": "uuid",
  "store_name": "string",
  "store_location": "string | null",
  "transaction_date": "ISO8601 date",
  "transaction_time": "HH:MM",
  "purchased_by": "Francisco | Loki",
  "line_items": [
    {
      "item_name": "string",
      "quantity": "number",
      "unit_price": "number",
      "total_price": "number",
      "matched_list_item_id": "uuid | null"
    }
  ],
  "subtotal": "number",
  "tax": "number",
  "total": "number",
  "payment_method": "string | null",
  "receipt_image_path": "string | null",
  "raw_ocr_text": "string | null",
  "created_at": "ISO8601 timestamp"
}
```

#### 1.4 Bought vs Still Needed Tracking
- **Automatic detection** from receipt OCR
- **Manual marking** for text-based purchases
- **Status sections** in list view:
  - **To Buy** — Current shopping list
  - **Bought This Trip** — Purchased but not yet archived
  - **Still Needed** — On list but not purchased
- **Confirmation flow** — "You bought 5 of 10 items. Still need: [list]"

#### 1.5 Output Formats
**Full Markdown** (file saved to disk):
```markdown
# Grocery List — Updated Jan 26, 2026

## To Buy

### Produce (Giant)
- 🍌 Bananas (3) — Aisle 1
- 🥑 Avocados (2, ripe) — Aisle 1

### Dairy (Giant)
- 🥛 Milk (Organic Valley, 1 gallon) — Aisle 6

## Bought This Trip (Jan 25)
- ✅ Eggs (dozen) — $4.99 @ Giant

## Still Needed from Last Trip
- Coffee beans (ran out before shopping)
```

**Channel-Optimized** (Telegram/Signal formatting):
- **Telegram**: Full markdown support (headers, lists, bold, italic, code)
- **Signal**: Basic formatting (bold, italic, strikethrough, monospace)
- Adapts based on chat platform detected

**Text-Only** (no formatting):
```
GROCERY LIST (Jan 26, 2026)

TO BUY:
Produce (Giant):
- Bananas (3)
- Avocados (2, ripe)

Dairy (Giant):
- Milk (Organic Valley, 1 gallon)

BOUGHT THIS TRIP (Jan 25):
- Eggs (dozen) - $4.99 @ Giant

STILL NEEDED:
- Coffee beans
```

### Phase 2: Intelligence & Analytics (Nice-to-Have)

#### 2.1 Purchase Frequency Analysis
- **Track purchase intervals** — "Milk: every 5.2 days (avg)"
- **Proactive suggestions** — "You usually buy eggs on Saturday, none on list"
- **Seasonal patterns** — "Strawberries typically bought May-July"
- **Out-of-cycle alerts** — "Been 10 days since milk purchase (avg: 5 days)"

**Data Model (Frequency):**
```json
{
  "item_name": "string",
  "category": "string",
  "average_days_between_purchases": "number",
  "last_purchased": "ISO8601 date",
  "next_expected_purchase": "ISO8601 date (calculated)",
  "purchase_history": [
    {"date": "ISO8601", "quantity": "number"}
  ],
  "confidence": "high | medium | low"
}
```

#### 2.2 Price Tracking & History
- **Historical prices** per item per store
- **Price trends** — "Eggs: +20% vs last month"
- **Best price identification** — "Lowest price: $2.99 @ Aldi (3 months ago)"
- **Inflation tracking** — Category-level price changes
- **Alert thresholds** — "Milk over $5/gallon — consider switching stores"

**Data Model (Price History):**
```json
{
  "item_name": "string",
  "store": "string",
  "price_points": [
    {
      "date": "ISO8601",
      "price": "number",
      "unit": "string",
      "sale": "boolean",
      "receipt_id": "uuid"
    }
  ],
  "current_price": "number",
  "average_price_30d": "number",
  "average_price_90d": "number",
  "lowest_price_ever": "number",
  "highest_price_ever": "number"
}
```

#### 2.3 Multi-Store Intelligence
- **Price comparison** — "Avocados: TJ's $1.49 vs Giant $2.29 — save $0.80"
- **Store preference per item** — Auto-suggest based on past purchases
- **Substitution mapping** — "Can't find X at Store A? Try Y at Store B"
- **Optimal shopping route** — "Buy produce at TJ's, dairy at Giant for best value"

#### 2.4 Spending Analytics
- **Total spending** — Weekly, monthly, yearly views
- **Category breakdown** — "Produce: $80 (18%), Dairy: $45 (10%)"
- **Budget tracking** — Set monthly budget, get alerts
- **Budget vs actual** — "This week: $125 (avg: $110) — $15 over"
- **Trend visualization** — Spending over time (markdown tables/charts in output)

**Data Model (Budget):**
```json
{
  "period": "weekly | monthly | yearly",
  "budget_amount": "number",
  "current_spending": "number",
  "remaining": "number",
  "alert_threshold": "number (percentage)",
  "category_budgets": {
    "produce": "number",
    "dairy": "number"
  }
}
```

#### 2.5 Smart Suggestions & Predictions
- **Restocking alerts** — "Low on milk (avg: 5 days, last: 4 days ago)"
- **Recipe integration** — "Planning pad thai? Need: rice noodles, peanuts, lime"
- **Seasonal optimization** — "Strawberries peak season (June) — currently 2x normal"
- **Bulk buying analysis** — "12-pack saves $4/month vs individual"

#### 2.6 Out-of-Stock Tracking
- **Manual logging** — "Couldn't find X at Store Y"
- **Pattern detection** — "Oat milk out of stock 3/5 trips at Giant"
- **Alternative suggestions** — "Oat milk unavailable? Try almond milk at TJ's"
- **Substitution history** — Track what was bought instead

**Data Model (Out of Stock):**
```json
{
  "item_name": "string",
  "store": "string",
  "date": "ISO8601",
  "substitution": "string | null",
  "reported_by": "Francisco | Loki"
}
```

### Phase 3: Advanced Household Features (Nice-to-Have)

#### 3.1 Inventory Management
- **Current stock** — "What's in the pantry/fridge?"
- **Quantity tracking** — "2 cans of beans, 1 bag of rice"
- **Expiration dates** (optional) — "Milk expires Jan 28"
- **Low stock alerts** — "Only 1 egg left, usually buy at 3"
- **Add to list from inventory** — "Running low on X → auto-add to list"

**Data Model (Inventory):**
```json
{
  "item_name": "string",
  "category": "string",
  "quantity": "number",
  "unit": "string",
  "location": "pantry | fridge | freezer",
  "expiration_date": "ISO8601 | null",
  "opened_date": "ISO8601 | null",
  "low_stock_threshold": "number",
  "purchased_date": "ISO8601",
  "receipt_id": "uuid"
}
```

#### 3.2 Waste Logging
- **Trip-based prompts** — "Going shopping? What didn't get used last time?"
- **Waste tracking** — Item, quantity, reason (spoiled, never used, etc.)
- **Waste reduction insights** — "You've wasted 3 bell peppers in 2 months — buy less?"
- **Cost of waste** — "$45 wasted this month"

**Data Model (Waste):**
```json
{
  "item_name": "string",
  "quantity": "number",
  "original_purchase_date": "ISO8601",
  "waste_logged_date": "ISO8601",
  "reason": "spoiled | never_used | overripe | other",
  "estimated_cost": "number",
  "logged_by": "Francisco | Loki"
}
```

#### 3.3 Use-It-Up Suggestions
- **Expiring soon** — "3 bell peppers expire tomorrow — recipe ideas?"
- **Recipe generation** — AI suggests recipes based on inventory
- **Prioritized list** — "Items to use first: [sorted by expiration]"

#### 3.4 Shared Household Preferences
- **Brand preferences by person** — "Francisco: Organic Valley, Loki: Horizon"
- **Dietary restrictions** — Allergies, vegetarian, vegan, gluten-free, etc.
- **Favorite items** — "Loki loves mango, Francisco prefers pineapple"
- **Purchase attribution** — "Who bought this receipt?"
- **Shopping history** — "Francisco shops Saturdays, Loki Wednesdays"

**Data Model (User Preferences):**
```json
{
  "user": "Francisco | Loki",
  "brand_preferences": {
    "milk": "Organic Valley",
    "eggs": "Vital Farms"
  },
  "dietary_restrictions": ["lactose_intolerant", "vegetarian"],
  "allergens": ["peanuts", "shellfish"],
  "favorite_items": ["mango", "dark_chocolate"],
  "shopping_patterns": {
    "typical_day": "Saturday",
    "typical_stores": ["Giant", "Trader Joe's"]
  }
}
```

#### 3.5 Budgeting & Financial Features
- **Monthly budget** — Set target, track progress
- **Category budgets** — Allocate by category
- **Budget alerts** — "Over budget by $45 this week"
- **Coupon/sale tracking** — "Eggs on sale at Giant ($3.99 → $2.99)"
- **Savings tracker** — "Saved $12 this month by shopping sales"

---

## Data Persistence Strategy

### Initial Implementation: JSON Files

**Directory Structure:**
```
grocery-tracker/
├── data/                          # User data (gitignored)
│   ├── current_list.json          # Active shopping list
│   ├── receipts/                  # Receipt data by date
│   │   ├── 2026-01-25_giant.json
│   │   └── 2026-01-26_traderjoes.json
│   ├── receipt_images/            # Uploaded receipt photos
│   │   ├── 2026-01-25_giant.jpg
│   │   └── 2026-01-26_traderjoes.jpg
│   ├── price_history.json         # Historical price data
│   ├── frequency_data.json        # Purchase frequency tracking
│   ├── inventory.json             # Current household inventory
│   ├── waste_log.json             # Waste tracking
│   ├── user_preferences.json      # Francisco & Loki preferences
│   └── budget.json                # Budget tracking
├── src/
│   └── grocery_tracker/           # Main package
│       ├── __init__.py
│       ├── main.py                # CLI entry point (Typer app)
│       ├── config.py              # Configuration management
│       ├── list_manager.py        # List operations
│       ├── receipt_processor.py   # Receipt data processing
│       ├── analytics.py           # Intelligence features
│       ├── inventory_manager.py   # Inventory tracking
│       ├── data_store.py          # JSON persistence layer
│       └── output_formatter.py    # Rich/JSON output formatting
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_list_manager.py       # Unit tests
│   ├── test_receipt_processor.py  # Unit tests
│   ├── test_data_persistence.py   # Unit tests
│   ├── test_cli.py                # CLI tests
│   └── test_integration.py        # Integration tests
├── .gitignore                     # Git ignore rules
├── config.toml.example            # Example config (committed)
├── pyproject.toml                 # Project config + dependencies
├── README.md                      # Usage documentation
└── uv.lock                        # Locked dependencies (auto-generated)
```

**Project Setup with uv:**

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# OR
pip install uv

# Clone or create project
mkdir grocery-tracker && cd grocery-tracker

# Initialize uv project
uv init

# Install dependencies from pyproject.toml
uv sync

# Install with dev dependencies
uv sync --all-extras

# Activate virtual environment (uv automatically creates one)
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Copy example config
cp config.toml.example ~/.config/grocery-tracker/config.toml
# Edit config as needed

# Run tests
uv run pytest

# Run CLI
uv run grocery --help

# Or after activating venv:
grocery --help
```

**pyproject.toml** (see Configuration Management section above for full file)

**Development Workflow:**

```bash
# Add a new dependency
uv add pydantic

# Add a dev dependency
uv add --dev pytest-asyncio

# Remove a dependency
uv remove pydantic

# Update dependencies
uv sync

# Run tests with coverage
uv run pytest --cov

# Run specific test
uv run pytest tests/test_list_manager.py -v

# Run linting
uv run ruff check src/

# Format code
uv run ruff format src/

# Build package
uv build

# Install package in editable mode
uv pip install -e .
```

**Why uv?**
- **10-100x faster** than pip for dependency resolution
- **Rust-based** for maximum performance
- **Lock file** (`uv.lock`) ensures reproducible builds
- **Built-in venv management** - no separate virtualenv needed
- **Pip-compatible** but much faster
- **Modern Python** best practices

### Future Migration: SQLite

**Rationale for migration:**
- Better query performance for analytics
- Relational data (items ↔ receipts ↔ price history)
- Transaction safety
- Easier complex queries (price trends, frequency analysis)

**Migration Timeline:** After MVP stable and tested

**Schema Design (Proposed):**
```sql
-- Core Tables
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    store TEXT,
    aisle TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE shopping_list (
    id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES items(id),
    quantity REAL,
    unit TEXT,
    brand_preference TEXT,
    estimated_price REAL,
    priority TEXT,
    added_by TEXT,
    added_at TEXT,
    status TEXT  -- 'to_buy', 'bought', 'still_needed'
);

CREATE TABLE receipts (
    id TEXT PRIMARY KEY,
    store_name TEXT,
    transaction_date TEXT,
    transaction_time TEXT,
    subtotal REAL,
    tax REAL,
    total REAL,
    purchased_by TEXT,
    image_path TEXT,
    created_at TEXT
);

CREATE TABLE receipt_items (
    id TEXT PRIMARY KEY,
    receipt_id TEXT REFERENCES receipts(id),
    item_name TEXT,
    quantity REAL,
    unit_price REAL,
    total_price REAL,
    matched_item_id TEXT REFERENCES items(id)
);

CREATE TABLE price_history (
    id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES items(id),
    store TEXT,
    price REAL,
    unit TEXT,
    date TEXT,
    on_sale BOOLEAN,
    receipt_id TEXT REFERENCES receipts(id)
);

CREATE TABLE inventory (
    id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES items(id),
    quantity REAL,
    unit TEXT,
    location TEXT,
    expiration_date TEXT,
    purchased_date TEXT,
    receipt_id TEXT REFERENCES receipts(id)
);

CREATE TABLE waste_log (
    id TEXT PRIMARY KEY,
    item_name TEXT,
    quantity REAL,
    waste_date TEXT,
    reason TEXT,
    cost REAL,
    logged_by TEXT
);

CREATE TABLE user_preferences (
    id TEXT PRIMARY KEY,
    user TEXT,
    preference_type TEXT,
    preference_key TEXT,
    preference_value TEXT
);

CREATE TABLE frequency_tracking (
    item_id TEXT PRIMARY KEY REFERENCES items(id),
    avg_days_between REAL,
    last_purchased TEXT,
    purchase_count INTEGER
);
```

---

## CLI Architecture & Output Modes

### Dual Output Strategy

The CLI supports two distinct output modes for different consumers:

#### 1. Rich Mode (Human-Readable)
**Default behavior** — Uses the `rich` library for beautiful terminal output
- Colored text, tables, progress bars
- Formatted markdown rendering
- Interactive prompts
- Visual hierarchy with panels and boxes
- Emoji support for better UX

#### 2. JSON Mode (Programmatic)
**Flag: `--json`** — Machine-readable structured output
- All responses returned as valid JSON
- Consumed by LLMs (Clawdbot)
- Programmatic integrations
- No ANSI colors or formatting
- Consistent schema

### Implementation Example

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
import json
import sys
from typing import Dict, Any

console = Console()

class OutputFormatter:
    def __init__(self, json_mode: bool = False):
        self.json_mode = json_mode
    
    def output(self, data: Dict[str, Any], message: str = ""):
        """Output data in appropriate format"""
        if self.json_mode:
            self._output_json(data)
        else:
            self._output_rich(data, message)
    
    def _output_json(self, data: Dict[str, Any]):
        """Output as JSON to stdout"""
        print(json.dumps(data, indent=2))
    
    def _output_rich(self, data: Dict[str, Any], message: str):
        """Output with Rich formatting"""
        if message:
            console.print(f"[green]✓[/green] {message}")
        
        # Format based on data type
        if 'items' in data:
            self._render_grocery_list(data)
        elif 'receipt' in data:
            self._render_receipt(data)
        elif 'stats' in data:
            self._render_stats(data)
    
    def _render_grocery_list(self, data: Dict):
        """Render grocery list with Rich"""
        table = Table(title="🛒 Grocery List", show_header=True)
        table.add_column("Item", style="cyan", no_wrap=False)
        table.add_column("Qty", style="magenta", justify="right")
        table.add_column("Store", style="green")
        table.add_column("Category", style="yellow")
        
        for item in data['items']:
            table.add_row(
                item['name'],
                str(item['quantity']),
                item['store'],
                item['category']
            )
        
        console.print(table)
    
    def _render_receipt(self, data: Dict):
        """Render receipt summary with Rich"""
        receipt = data['receipt']
        
        panel = Panel(
            f"""[bold]{receipt['store_name']}[/bold]
            
Date: {receipt['transaction_date']} {receipt['transaction_time']}
Items: {len(receipt['line_items'])}
Total: ${receipt['total']:.2f}""",
            title="📄 Receipt Processed",
            border_style="green"
        )
        
        console.print(panel)
        
        # Show items table
        table = Table(show_header=True)
        table.add_column("Item")
        table.add_column("Qty", justify="right")
        table.add_column("Price", justify="right")
        
        for item in receipt['line_items']:
            table.add_row(
                item['item_name'],
                str(item['quantity']),
                f"${item['total_price']:.2f}"
            )
        
        console.print(table)
    
    def error(self, message: str):
        """Output error message"""
        if self.json_mode:
            print(json.dumps({"error": message, "success": False}))
        else:
            console.print(f"[red]✗ Error:[/red] {message}")
    
    def success(self, message: str, data: Dict = None):
        """Output success message"""
        if self.json_mode:
            output = {"success": True, "message": message}
            if data:
                output["data"] = data
            print(json.dumps(output))
        else:
            console.print(f"[green]✓[/green] {message}")
```

### CLI Commands with Output Modes

```bash
# Rich mode (default) - Human readable
grocery add "bananas" --quantity 3 --store Giant

# JSON mode - Machine readable
grocery add "bananas" --quantity 3 --store Giant --json

# View list (Rich with table)
grocery list

# View list (JSON for LLM consumption)
grocery list --json

# Receipt processing (Rich with progress)
grocery receipt upload ./receipt.jpg

# Receipt processing (JSON response)
grocery receipt upload ./receipt.jpg --json

# Analytics (Rich with charts/tables)
grocery stats --item milk

# Analytics (JSON data)
grocery stats --item milk --json
```

### JSON Response Schemas

#### Add Item Response
```json
{
  "success": true,
  "message": "Added bananas to grocery list",
  "data": {
    "item": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Bananas",
      "quantity": 3,
      "store": "Giant",
      "category": "Produce",
      "added_at": "2026-01-26T10:30:00Z"
    }
  }
}
```

#### List View Response
```json
{
  "success": true,
  "data": {
    "list": {
      "version": "1.0",
      "last_updated": "2026-01-26T10:30:00Z",
      "items": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "name": "Bananas",
          "quantity": 3,
          "unit": "count",
          "category": "Produce",
          "store": "Giant",
          "status": "to_buy"
        }
      ]
    }
  }
}
```

#### Receipt Processing Response
```json
{
  "success": true,
  "message": "Receipt processed successfully",
  "data": {
    "receipt": {
      "id": "receipt-550e8400-e29b-41d4-a716-446655440010",
      "store_name": "Giant Food",
      "transaction_date": "2026-01-25",
      "total": 42.57,
      "items_count": 8
    },
    "reconciliation": {
      "matched_items": 5,
      "still_needed": ["milk", "eggs", "bread"],
      "newly_bought": ["bananas", "yogurt", "chicken", "rice", "pasta"]
    }
  }
}
```

#### Error Response
```json
{
  "success": false,
  "error": "Item 'bananas' already exists on the list",
  "error_code": "DUPLICATE_ITEM",
  "suggestion": "Use 'grocery update' to modify quantity"
}
```

### CLI Framework Choice: Typer

**Recommendation: `typer`** (built on Click)

**Benefits:**
- Type hints for automatic validation
- Automatic `--json` flag support
- Beautiful help messages (with Rich integration)
- Subcommand organization
- Progress bars and spinners

**Example Implementation:**

```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer()
formatter = OutputFormatter()

@app.callback()
def main(json: bool = typer.Option(False, "--json", help="Output as JSON")):
    """Grocery Tracker CLI"""
    global formatter
    formatter = OutputFormatter(json_mode=json)

@app.command()
def add(
    item: str = typer.Argument(..., help="Item name"),
    quantity: Optional[float] = typer.Option(None, "--quantity", "-q"),
    store: Optional[str] = typer.Option(None, "--store", "-s"),
    category: Optional[str] = typer.Option(None, "--category", "-c"),
):
    """Add item to grocery list"""
    try:
        result = grocery_manager.add_item(item, quantity, store, category)
        formatter.success(f"Added {item} to grocery list", result)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)

@app.command()
def list(
    store: Optional[str] = typer.Option(None, "--store", "-s"),
    category: Optional[str] = typer.Option(None, "--category", "-c"),
):
    """View grocery list"""
    try:
        items = grocery_manager.get_list(store=store, category=category)
        formatter.output({"items": items})
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)

@app.command()
def receipt(
    action: str = typer.Argument(..., help="upload or parse"),
    source: str = typer.Argument(..., help="Image path or text description"),
):
    """Process receipt"""
    try:
        if action == "upload":
            result = receipt_processor.process_image(Path(source))
        elif action == "parse":
            result = receipt_processor.process_text(source)
        else:
            raise ValueError(f"Invalid action: {action}")
        
        formatter.output({"receipt": result})
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
```

### Rich Output Examples

**Adding Item (Rich):**
```
✓ Added bananas to grocery list

╭─────────────────────────────╮
│  Item: Bananas              │
│  Quantity: 3                │
│  Store: Giant               │
│  Category: Produce          │
│  Added: 2026-01-26 10:30    │
╰─────────────────────────────╯
```

**Listing Items (Rich):**
```
                🛒 Grocery List                
┏━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Item       ┃ Qty ┃ Store     ┃ Category ┃
┡━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ Bananas    │   3 │ Giant     │ Produce  │
│ Milk       │   1 │ Giant     │ Dairy    │
│ Eggs       │  12 │ Giant     │ Dairy    │
└────────────┴─────┴───────────┴──────────┘

Total items: 3
```

**Processing Receipt (Rich with Progress):**
```
Processing receipt... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

╭────────── 📄 Receipt Processed ──────────╮
│                                           │
│  Giant Food                               │
│                                           │
│  Date: 2026-01-25 14:32                  │
│  Items: 8                                 │
│  Total: $42.57                           │
╰───────────────────────────────────────────╯

┏━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━┓
┃ Item         ┃ Qty ┃ Price  ┃
┡━━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━┩
│ Bananas      │   3 │  $1.47 │
│ Milk         │   1 │  $5.49 │
│ Eggs         │  12 │  $4.99 │
└──────────────┴─────┴────────┘

✓ Matched 5 items from your list
⚠ Still needed: milk, eggs, bread
```

---

## Output Format Specifications

### Telegram Markdown Support
- **Bold**: `**text**` or `__text__`
- **Italic**: `*text*` or `_text_`
- **Inline code**: `` `text` ``
- **Code block**: ` ```language\ncode\n``` `
- **Links**: `[text](URL)`
- **Lists**: Standard markdown `- item` or `1. item`
- **Headers**: `# H1`, `## H2`, `### H3`

### Signal Formatting Support
- **Bold**: `**text**`
- **Italic**: `*text*`
- **Strikethrough**: `~~text~~`
- **Monospace**: `` `text` ``
- Limited list support, prefer plain text with bullets (•)

### Format Detection Logic
```python
def detect_chat_platform(context):
    """Determine which chat platform is being used"""
    # Logic to detect Telegram vs Signal vs other
    # Return format spec for that platform
    pass

def format_list(items, platform="telegram"):
    """Format grocery list based on platform capabilities"""
    if platform == "telegram":
        return format_telegram_markdown(items)
    elif platform == "signal":
        return format_signal_basic(items)
    else:
        return format_text_only(items)
```

---

## Receipt Processing Architecture

### Skill-Level Preprocessing

Receipt image analysis is handled **at the skill layer** by the LLM agent before invoking the CLI. The Python application receives only structured JSON data.

**Architecture Flow:**
1. User uploads receipt image to chat
2. **Skill layer (SKILL.md instructions)**: Agent uses vision capabilities to extract data
3. **Skill layer**: Agent formats extracted data as JSON
4. **Skill layer**: Agent invokes CLI with `grocery receipt process --data <json>`
5. **CLI layer**: Python processes structured data, no API calls

**Benefits:**
- Clean separation: Skill handles multimodal, CLI handles business logic
- No API keys needed in Python app (handled by agent's own credentials)
- CLI is pure data processing - testable without API mocks
- Subagent spawning handled by skill orchestration

### Skill Instructions (Preview)

The SKILL.md will contain instructions like:

```markdown
## Receipt Processing Workflow

When user uploads a receipt image:

1. **Extract data using your vision capabilities**
   - Analyze the image to identify store, date, items, prices
   - Structure the data according to the schema below

2. **Format as JSON**
   ```json
   {
     "store_name": "string",
     "transaction_date": "YYYY-MM-DD",
     "transaction_time": "HH:MM",
     "line_items": [
       {
         "item_name": "string",
         "quantity": number,
         "unit_price": number,
         "total_price": number
       }
     ],
     "subtotal": number,
     "tax": number,
     "total": number
   }
   ```

3. **Invoke CLI with structured data**
   ```bash
   grocery receipt process --data '{"store_name": "Giant", ...}'
   ```

4. **Return results to user**
   - Show what was matched from list
   - Show what's still needed
   - Display receipt summary
```

### Python CLI Interface

The CLI simply accepts structured JSON:

```python
# src/receipt_processor.py
from typing import Dict
from pydantic import BaseModel, Field
from datetime import date, time

class LineItem(BaseModel):
    item_name: str
    quantity: float = 1.0
    unit_price: float
    total_price: float

class ReceiptData(BaseModel):
    store_name: str
    store_location: str | None = None
    transaction_date: date
    transaction_time: time | None = None
    line_items: list[LineItem]
    subtotal: float
    tax: float = 0.0
    total: float
    payment_method: str | None = None

class ReceiptProcessor:
    def __init__(self, list_manager, data_store):
        self.list_manager = list_manager
        self.data_store = data_store
    
    def process_receipt(self, receipt_data: ReceiptData) -> Dict:
        """
        Process structured receipt data
        
        Args:
            receipt_data: Validated receipt data from skill layer
            
        Returns:
            Reconciliation results
        """
        # Save receipt
        receipt_id = self.data_store.save_receipt(receipt_data.model_dump())
        
        # Match items with shopping list
        matched_items = []
        still_needed = []
        
        current_list = self.list_manager.get_list()
        
        for list_item in current_list['items']:
            # Try to match with receipt items
            matched = False
            for receipt_item in receipt_data.line_items:
                if self._items_match(list_item['name'], receipt_item.item_name):
                    matched_items.append(list_item)
                    # Mark as bought
                    self.list_manager.mark_bought(list_item['id'], receipt_item.quantity)
                    matched = True
                    break
            
            if not matched:
                still_needed.append(list_item['name'])
        
        # Update price history
        for item in receipt_data.line_items:
            self._update_price_history(
                item.item_name,
                receipt_data.store_name,
                item.unit_price,
                receipt_data.transaction_date
            )
        
        return {
            "receipt_id": receipt_id,
            "matched_items": len(matched_items),
            "still_needed": still_needed,
            "total_spent": receipt_data.total,
            "items_purchased": len(receipt_data.line_items)
        }
    
    def _items_match(self, list_name: str, receipt_name: str) -> bool:
        """Fuzzy match item names"""
        # Simple matching for MVP - can be enhanced
        list_normalized = list_name.lower().strip()
        receipt_normalized = receipt_name.lower().strip()
        
        return (
            list_normalized == receipt_normalized or
            list_normalized in receipt_normalized or
            receipt_normalized in list_normalized
        )
    
    def _update_price_history(self, item_name: str, store: str, 
                             price: float, date: date):
        """Update price history for item"""
        # Implementation details...
        pass
```

### CLI Command

```python
# src/main.py (Typer CLI)
import json
from typing import Optional

@app.command()
def receipt(
    action: str = typer.Argument(..., help="process"),
    data: Optional[str] = typer.Option(None, "--data", help="JSON receipt data"),
    file: Optional[Path] = typer.Option(None, "--file", help="Path to JSON file"),
):
    """
    Process receipt data
    
    Data should be provided either via --data flag (JSON string) or --file flag
    """
    try:
        if action != "process":
            raise ValueError(f"Unknown action: {action}")
        
        # Load data
        if data:
            receipt_dict = json.loads(data)
        elif file:
            with open(file) as f:
                receipt_dict = json.load(f)
        else:
            raise ValueError("Must provide either --data or --file")
        
        # Validate and process
        receipt_data = ReceiptData(**receipt_dict)
        result = receipt_processor.process_receipt(receipt_data)
        
        formatter.output({
            "receipt": receipt_dict,
            "reconciliation": result
        }, f"Processed receipt from {receipt_data.store_name}")
        
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)
```

### Example Usage (from Skill)

```bash
# Skill extracts this JSON from receipt image:
RECEIPT_JSON='{
  "store_name": "Giant Food",
  "transaction_date": "2026-01-25",
  "transaction_time": "14:32",
  "line_items": [
    {"item_name": "Bananas", "quantity": 3, "unit_price": 0.49, "total_price": 1.47},
    {"item_name": "Milk", "quantity": 1, "unit_price": 5.49, "total_price": 5.49}
  ],
  "subtotal": 6.96,
  "tax": 0.00,
  "total": 6.96
}'

# Skill then calls:
grocery receipt process --data "$RECEIPT_JSON" --json

# Returns:
# {
#   "success": true,
#   "data": {
#     "receipt_id": "receipt-123",
#     "matched_items": 2,
#     "still_needed": ["eggs", "bread"],
#     "total_spent": 6.96
#   }
# }
```

### No API Dependencies

The Python application has **zero external API dependencies**:
- No `anthropic` package needed
- No API key management
- All multimodal work done by the agent invoking the CLI
- CLI is pure business logic and data processing

This makes the application:
- Faster (no API latency)
- Cheaper (no API costs from the app)
- More testable (no API mocks needed)
- More portable (works with any LLM agent that can extract receipt data)

---

## Error Handling & Edge Cases

### Duplicate Items
**Scenario:** User adds "milk" but "milk" already on list  
**Handling:**
```
⚠️ "milk" is already on the grocery list (1 gallon, Giant).
What would you like to do?
1. Increase quantity (make it 2 gallons)
2. Add separate entry (different brand/store)
3. Ignore (keep existing entry)
Reply with 1, 2, or 3.
```

### Ambiguous Store
**Scenario:** Item added without store specification  
**Handling:**
```
📍 Which store should I add "bananas" to?
1. Giant (most frequent for Produce)
2. Trader Joe's
3. Whole Foods
4. Other (specify)
Reply with number or store name.
```

### Receipt OCR Failures
**Scenario:** OCR confidence low or text unreadable  
**Handling:**
```
⚠️ Receipt OCR had low confidence. Please review:

Extracted:
- Store: Giant (?)
- Total: $42.57
- Items: milk $3.99, eggz $4.99 (likely "eggs")

Send "confirm" to accept, or provide corrections:
"eggs not eggz, add bread $2.49"
```

### Missing Price Data
**Scenario:** Item on list but no historical price  
**Handling:**
- Use estimated price if provided
- Show "Price unknown" in list
- Request price after purchase

### Out of Stock Items
**Scenario:** User couldn't find item at store  
**Handling:**
```
Couldn't find an item? Let me know:
"out of stock: oat milk at Giant"

I'll:
1. Log the out-of-stock occurrence
2. Keep it on your list for next trip
3. Suggest alternatives if available
```

---

## Security & Privacy Considerations

### Data Storage
- All data stored locally on server filesystem
- No cloud syncing unless explicitly configured
- Receipt images stored with generated UUIDs (not personal info in filename)

### Sensitive Information
- Payment methods stored optionally (user consent)
- No credit card numbers or payment tokens stored
- Receipt images can be deleted after OCR if user prefers

### Access Control
- Group chat access controlled by Clawdbot configuration
- Only allowlisted users can interact
- User attribution tracked for audit purposes

### Data Retention
- User can request data export (JSON format)
- User can request data deletion
- Configurable retention periods for old receipts/history

---

## Testing Strategy (REQUIRED FOR MVP)

### Critical Testing Requirements

**Unit and integration tests are MANDATORY for MVP release.** These tests enable:
- Autonomous Claude instances to validate their implementations
- Confident refactoring and feature additions
- Regression detection
- Documentation of expected behavior

### Test Framework: pytest

**Required Coverage:**
- Core business logic: 90%+ coverage
- CLI commands: 100% coverage (all commands tested)
- Data persistence: 100% coverage
- Receipt processing: Edge cases thoroughly tested

### Unit Tests (Required)

#### Item Management Tests
```python
# tests/test_list_manager.py
import pytest
from src.list_manager import ListManager
from datetime import datetime

class TestListManager:
    @pytest.fixture
    def manager(self):
        """Fresh list manager for each test"""
        return ListManager(data_dir="./test_data")
    
    def test_add_item_success(self, manager):
        """Test adding a new item"""
        result = manager.add_item(
            name="Bananas",
            quantity=3,
            store="Giant",
            category="Produce"
        )
        
        assert result['success'] == True
        assert result['data']['item']['name'] == "Bananas"
        assert result['data']['item']['quantity'] == 3
        assert 'id' in result['data']['item']
    
    def test_add_duplicate_item(self, manager):
        """Test adding duplicate item raises error"""
        manager.add_item("Milk", 1, "Giant", "Dairy")
        
        with pytest.raises(ValueError, match="already exists"):
            manager.add_item("Milk", 1, "Giant", "Dairy")
    
    def test_remove_item_success(self, manager):
        """Test removing an existing item"""
        added = manager.add_item("Eggs", 12, "Giant", "Dairy")
        item_id = added['data']['item']['id']
        
        result = manager.remove_item(item_id)
        
        assert result['success'] == True
        assert len(manager.get_list()['items']) == 0
    
    def test_remove_nonexistent_item(self, manager):
        """Test removing nonexistent item raises error"""
        with pytest.raises(ValueError, match="not found"):
            manager.remove_item("fake-uuid")
    
    def test_mark_as_bought(self, manager):
        """Test marking item as bought"""
        added = manager.add_item("Bread", 1, "Giant", "Bakery")
        item_id = added['data']['item']['id']
        
        result = manager.mark_bought(item_id, quantity=1)
        
        assert result['success'] == True
        item = manager.get_item(item_id)
        assert item['status'] == 'bought'
    
    def test_get_list_by_store(self, manager):
        """Test filtering list by store"""
        manager.add_item("Avocados", 2, "Trader Joe's", "Produce")
        manager.add_item("Milk", 1, "Giant", "Dairy")
        manager.add_item("Eggs", 12, "Giant", "Dairy")
        
        tj_items = manager.get_list(store="Trader Joe's")
        assert len(tj_items['items']) == 1
        assert tj_items['items'][0]['name'] == "Avocados"
        
        giant_items = manager.get_list(store="Giant")
        assert len(giant_items['items']) == 2
    
    def test_get_list_by_category(self, manager):
        """Test filtering list by category"""
        manager.add_item("Bananas", 3, "Giant", "Produce")
        manager.add_item("Milk", 1, "Giant", "Dairy")
        manager.add_item("Avocados", 2, "Giant", "Produce")
        
        produce = manager.get_list(category="Produce")
        assert len(produce['items']) == 2
```

#### Receipt Processing Tests
```python
# tests/test_receipt_processor.py
import pytest
from src.grocery_tracker.receipt_processor import ReceiptProcessor, ReceiptData, LineItem
from datetime import date, time

class TestReceiptProcessor:
    @pytest.fixture
    def processor(self, tmp_path):
        """Processor with test data store"""
        from src.grocery_tracker.data_store import DataStore
        from src.grocery_tracker.list_manager import ListManager
        
        data_store = DataStore(data_dir=tmp_path)
        list_manager = ListManager(data_store)
        
        return ReceiptProcessor(list_manager, data_store)
    
    def test_process_receipt_valid_data(self, processor):
        """Test processing receipt with valid structured data"""
        receipt_data = ReceiptData(
            store_name="Giant Food",
            transaction_date=date(2026, 1, 25),
            transaction_time=time(14, 32),
            line_items=[
                LineItem(item_name="Bananas", quantity=3, unit_price=0.49, total_price=1.47),
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49)
            ],
            subtotal=6.96,
            tax=0.00,
            total=6.96
        )
        
        result = processor.process_receipt(receipt_data)
        
        assert result['total_spent'] == 6.96
        assert result['items_purchased'] == 2
        assert 'receipt_id' in result
    
    def test_process_receipt_with_list_matching(self, processor):
        """Test receipt processing matches items on list"""
        # Add items to list
        processor.list_manager.add_item("Bananas", 3, "Giant", "Produce")
        processor.list_manager.add_item("Milk", 1, "Giant", "Dairy")
        processor.list_manager.add_item("Eggs", 12, "Giant", "Dairy")
        
        # Process receipt with only 2 items
        receipt_data = ReceiptData(
            store_name="Giant Food",
            transaction_date=date(2026, 1, 25),
            line_items=[
                LineItem(item_name="Bananas", quantity=3, unit_price=0.49, total_price=1.47),
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49)
            ],
            subtotal=6.96,
            tax=0.00,
            total=6.96
        )
        
        result = processor.process_receipt(receipt_data)
        
        assert result['matched_items'] == 2
        assert "Eggs" in result['still_needed']
        assert "Bananas" not in result['still_needed']
    
    def test_item_matching_fuzzy(self, processor):
        """Test fuzzy matching of item names"""
        # List has "Milk" but receipt has "WHOLE MILK"
        processor.list_manager.add_item("Milk", 1, "Giant", "Dairy")
        
        receipt_data = ReceiptData(
            store_name="Giant Food",
            transaction_date=date(2026, 1, 25),
            line_items=[
                LineItem(item_name="WHOLE MILK", quantity=1, unit_price=5.49, total_price=5.49)
            ],
            subtotal=5.49,
            tax=0.00,
            total=5.49
        )
        
        result = processor.process_receipt(receipt_data)
        
        assert result['matched_items'] == 1
        assert len(result['still_needed']) == 0
    
    def test_price_history_update(self, processor):
        """Test that price history is updated after receipt"""
        receipt_data = ReceiptData(
            store_name="Giant Food",
            transaction_date=date(2026, 1, 25),
            line_items=[
                LineItem(item_name="Milk", quantity=1, unit_price=5.49, total_price=5.49)
            ],
            subtotal=5.49,
            tax=0.00,
            total=5.49
        )
        
        processor.process_receipt(receipt_data)
        
        # Verify price was recorded
        # (actual implementation will depend on data_store structure)
        price_history = processor.data_store.load_price_history()
        assert len(price_history) > 0
    
    def test_invalid_receipt_data(self, processor):
        """Test validation of receipt data"""
        with pytest.raises(ValueError):
            # Missing required fields
            ReceiptData(
                store_name="Giant",
                transaction_date=date(2026, 1, 25),
                line_items=[],  # Empty items
                total=0.0
            )
```

#### Data Persistence Tests
```python
# tests/test_data_persistence.py
import pytest
from src.data_store import DataStore
import json
from pathlib import Path

class TestDataPersistence:
    @pytest.fixture
    def store(self, tmp_path):
        """Create temporary data store"""
        return DataStore(data_dir=tmp_path)
    
    def test_save_and_load_list(self, store):
        """Test saving and loading grocery list"""
        test_data = {
            "version": "1.0",
            "items": [
                {"id": "123", "name": "Milk", "quantity": 1}
            ]
        }
        
        store.save_list(test_data)
        loaded = store.load_list()
        
        assert loaded == test_data
    
    def test_save_receipt(self, store):
        """Test saving receipt data"""
        receipt = {
            "id": "receipt-123",
            "store_name": "Giant",
            "total": 42.57
        }
        
        store.save_receipt(receipt)
        loaded = store.load_receipt("receipt-123")
        
        assert loaded == receipt
    
    def test_concurrent_writes(self, store):
        """Test handling concurrent writes safely"""
        # Simulate multiple writes
        for i in range(10):
            store.save_list({"items": [{"id": str(i)}]})
        
        # Should have latest data
        loaded = store.load_list()
        assert loaded['items'][0]['id'] == "9"
```

### Integration Tests (Required)

```python
# tests/test_integration.py
import pytest
from src.main import GroceryTracker
from pathlib import Path

class TestEndToEndWorkflows:
    @pytest.fixture
    def tracker(self, tmp_path):
        """Create tracker with temporary storage"""
        return GroceryTracker(data_dir=tmp_path)
    
    def test_complete_shopping_workflow(self, tracker):
        """Test full workflow: add items, process receipt, reconcile"""
        # Add items to list
        tracker.add_item("Bananas", 3, "Giant", "Produce")
        tracker.add_item("Milk", 1, "Giant", "Dairy")
        tracker.add_item("Eggs", 12, "Giant", "Dairy")
        
        # Simulate receipt processing (mock)
        receipt_data = {
            "store_name": "Giant",
            "transaction_date": "2026-01-26",
            "line_items": [
                {"item_name": "Bananas", "quantity": 3, "total_price": 1.47},
                {"item_name": "Milk", "quantity": 1, "total_price": 5.49}
            ],
            "total": 6.96
        }
        
        result = tracker.process_receipt(receipt_data)
        
        # Verify reconciliation
        assert len(result['matched_items']) == 2
        assert "Eggs" in result['still_needed']
        
        # Verify list updated
        list_data = tracker.get_list()
        banana_item = next(i for i in list_data['items'] if i['name'] == "Bananas")
        assert banana_item['status'] == 'bought'
    
    def test_price_tracking_workflow(self, tracker):
        """Test price history accumulation"""
        # Add milk, buy multiple times
        tracker.add_item("Milk", 1, "Giant", "Dairy")
        
        # First purchase
        tracker.process_receipt({
            "store_name": "Giant",
            "transaction_date": "2026-01-15",
            "line_items": [{"item_name": "Milk", "quantity": 1, "total_price": 5.49}],
            "total": 5.49
        })
        
        # Second purchase
        tracker.process_receipt({
            "store_name": "Giant",
            "transaction_date": "2026-01-20",
            "line_items": [{"item_name": "Milk", "quantity": 1, "total_price": 5.99}],
            "total": 5.99
        })
        
        # Check price history
        history = tracker.get_price_history("Milk", "Giant")
        assert len(history['price_points']) == 2
        assert history['price_points'][0]['price'] == 5.49
        assert history['price_points'][1]['price'] == 5.99
```

### CLI Tests (Required)

```python
# tests/test_cli.py
import pytest
from typer.testing import CliRunner
from src.main import app

runner = CliRunner()

class TestCLI:
    def test_add_item_json_output(self):
        """Test add command with JSON flag"""
        result = runner.invoke(app, [
            "add", "Bananas",
            "--quantity", "3",
            "--store", "Giant",
            "--json"
        ])
        
        assert result.exit_code == 0
        
        import json
        output = json.loads(result.stdout)
        assert output['success'] == True
        assert output['data']['item']['name'] == "Bananas"
    
    def test_list_command_json(self):
        """Test list command with JSON output"""
        # Add item first
        runner.invoke(app, ["add", "Milk", "--json"])
        
        result = runner.invoke(app, ["list", "--json"])
        
        assert result.exit_code == 0
        
        import json
        output = json.loads(result.stdout)
        assert 'data' in output
        assert 'list' in output['data']
        assert len(output['data']['list']['items']) > 0
    
    def test_error_handling_json(self):
        """Test error response in JSON format"""
        result = runner.invoke(app, [
            "remove", "nonexistent-item",
            "--json"
        ])
        
        assert result.exit_code == 1
        
        import json
        output = json.loads(result.stdout)
        assert output['success'] == False
        assert 'error' in output
```

### Test Coverage Requirements

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Minimum coverage requirements:
# - Core logic (list_manager, receipt_processor): 90%
# - CLI commands: 100%
# - Data persistence: 100%
# - Overall project: 85%
```

### Continuous Testing

```python
# pytest.ini configuration
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --cov=src
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=85

# Mark slow tests
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
```

### Mock Data Fixtures

```python
# tests/conftest.py
import pytest
from pathlib import Path
import json
from datetime import date, time

@pytest.fixture
def sample_receipt_data():
    """Sample receipt data for testing"""
    return {
        "store_name": "Giant Food",
        "transaction_date": "2026-01-25",
        "transaction_time": "14:32",
        "line_items": [
            {"item_name": "Bananas", "quantity": 3, "unit_price": 0.49, "total_price": 1.47},
            {"item_name": "Milk", "quantity": 1, "unit_price": 5.49, "total_price": 5.49}
        ],
        "subtotal": 6.96,
        "tax": 0.00,
        "total": 6.96
    }

@pytest.fixture
def sample_receipt_obj(sample_receipt_data):
    """Sample receipt as ReceiptData object"""
    from src.grocery_tracker.receipt_processor import ReceiptData, LineItem
    
    return ReceiptData(
        store_name=sample_receipt_data['store_name'],
        transaction_date=date(2026, 1, 25),
        transaction_time=time(14, 32),
        line_items=[
            LineItem(**item) for item in sample_receipt_data['line_items']
        ],
        subtotal=sample_receipt_data['subtotal'],
        tax=sample_receipt_data['tax'],
        total=sample_receipt_data['total']
    )

@pytest.fixture
def sample_grocery_list():
    """Sample grocery list for testing"""
    return {
        "version": "1.0",
        "items": [
            {
                "id": "test-123",
                "name": "Bananas",
                "quantity": 3,
                "category": "Produce",
                "store": "Giant",
                "status": "to_buy"
            }
        ]
    }

@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory structure"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "receipts").mkdir()
    (data_dir / "receipt_images").mkdir()
    return data_dir
```

### Why Testing is Critical for Autonomous Development

1. **Self-Validation** — Claude instances can run tests to verify their implementations
2. **Regression Prevention** — Changes don't break existing functionality
3. **Documentation** — Tests serve as executable documentation
4. **Confidence** — Enables bold refactoring and optimization
5. **Debugging** — Failing tests pinpoint exactly what broke

---

## Success Metrics

### MVP Success Criteria
- ✅ Can add/remove/view items without errors
- ✅ Receipt processing via LLM extracts data accurately (>90% accuracy)
- ✅ List correctly reconciles bought vs needed items
- ✅ Both Rich and JSON output modes work correctly
- ✅ Zero data loss (all transactions persist correctly)
- ✅ **Unit tests: 90%+ coverage on core logic**
- ✅ **Integration tests: All major workflows tested**
- ✅ **CLI tests: 100% command coverage**
- ✅ **All tests pass consistently**

### Phase 2 Success Criteria
- ✅ Purchase frequency predictions within 1-2 day accuracy
- ✅ Price tracking shows clear trends over 30+ days
- ✅ Budget alerts trigger correctly based on thresholds
- ✅ Multi-store recommendations save >$10/month

### User Satisfaction Metrics
- Reduces time spent managing grocery lists by 50%
- Eliminates forgotten items (capture rate >95%)
- Provides actionable insights (users act on 3+ suggestions/month)
- Waste reduction of 20% after 3 months of use

---

## Future Enhancements (Out of Scope for v1)

### Advanced Analytics
- Nutrition tracking (calories, macros from purchased items)
- Carbon footprint estimation
- Meal planning integration
- Recipe cost calculator

### External Integrations
- Notion database sync (Francisco uses Notion heavily)
- Google Sheets export
- YNAB/Mint budget sync
- Instacart/grocery delivery API integration

### Machine Learning
- Predictive restocking (more sophisticated than frequency)
- Receipt auto-categorization without rules
- Price trend forecasting
- Personalized recommendation engine

### Collaborative Features
- Shared shopping assignments ("Loki, can you grab milk?")
- Real-time list syncing (both can edit simultaneously)
- Shopping trip coordination ("Who's going when?")

---

## Open Questions & Decisions Needed

### 1. OCR Confidence Threshold
**Question:** What confidence score should trigger manual review?  
**Options:** 70%, 80%, 90%  
**Decision:** Start with 80%, adjust based on testing

### 2. Default Store Assignment
**Question:** How to handle items without specified store?  
**Options:**
- Always prompt user
- Use most frequent store for category
- Use last-used store
**Decision:** TBD based on user preference

### 3. Price Update Frequency
**Question:** How often to update price averages?  
**Options:** After each receipt, daily batch, weekly  
**Decision:** After each receipt (real-time)

### 4. Expiration Tracking Scope
**Question:** Track expiration for all items or opt-in?  
**Options:** 
- Opt-in only (manual entry)
- Auto-track common perishables (dairy, produce)
- Never track (too tedious)
**Decision:** Opt-in for select items

### 5. JSON to SQLite Migration Timeline
**Question:** When to migrate from JSON to SQLite?  
**Options:** After MVP, after Phase 2, never  
**Decision:** After MVP is stable and tested (~1-2 months)

---

## Appendix A: Example Data Files

### current_list.json
```json
{
  "version": "1.0",
  "last_updated": "2026-01-26T10:30:00Z",
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Bananas",
      "quantity": 3,
      "unit": "count",
      "category": "Produce",
      "store": "Giant",
      "aisle": "1",
      "brand_preference": null,
      "estimated_price": 0.49,
      "priority": "medium",
      "added_by": "Francisco",
      "added_at": "2026-01-25T08:15:00Z",
      "notes": null,
      "status": "to_buy"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Milk",
      "quantity": 1,
      "unit": "gallon",
      "category": "Dairy",
      "store": "Giant",
      "aisle": "6",
      "brand_preference": "Organic Valley",
      "estimated_price": 5.49,
      "priority": "high",
      "added_by": "Loki",
      "added_at": "2026-01-26T07:00:00Z",
      "notes": "Whole milk",
      "status": "to_buy"
    }
  ]
}
```

### 2026-01-25_giant.json
```json
{
  "id": "receipt-550e8400-e29b-41d4-a716-446655440010",
  "store_name": "Giant Food",
  "store_location": "Rockville, MD",
  "transaction_date": "2026-01-25",
  "transaction_time": "14:32",
  "purchased_by": "Francisco",
  "line_items": [
    {
      "item_name": "BANANAS",
      "quantity": 3,
      "unit_price": 0.49,
      "total_price": 1.47,
      "matched_list_item_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    {
      "item_name": "EGGS LARGE DOZEN",
      "quantity": 1,
      "unit_price": 4.99,
      "total_price": 4.99,
      "matched_list_item_id": null
    }
  ],
  "subtotal": 6.46,
  "tax": 0.00,
  "total": 6.46,
  "payment_method": "Credit",
  "receipt_image_path": "./data/receipt_images/2026-01-25_giant.jpg",
  "raw_ocr_text": "GIANT FOOD\n123 Main St\nRockville MD\n\n01/25/2026 14:32\n\nBANANAS    $0.49 x3    $1.47\nEGGS LG DZ $4.99       $4.99\n\nSUBTOTAL              $6.46\nTAX                   $0.00\nTOTAL                 $6.46\n\nCREDIT CARD          $6.46",
  "created_at": "2026-01-25T14:45:00Z"
}
```

---

## Appendix B: User Preference Examples

### Francisco's Preferences
```json
{
  "user": "Francisco",
  "brand_preferences": {
    "milk": "Organic Valley",
    "eggs": "Vital Farms",
    "coffee": "Lavazza",
    "protein_powder": "Optimum Nutrition Gold Standard"
  },
  "dietary_restrictions": [],
  "allergens": [],
  "favorite_items": [
    "dark_chocolate",
    "avocados",
    "greek_yogurt"
  ],
  "shopping_patterns": {
    "typical_days": ["Tuesday", "Saturday"],
    "typical_stores": ["Giant", "Trader Joe's"],
    "avg_trip_frequency_days": 4,
    "preferred_time": "morning"
  },
  "budget_preferences": {
    "monthly_budget": 500,
    "alert_threshold": 0.9,
    "track_by_category": true
  }
}
```

### Loki's Preferences
```json
{
  "user": "Loki",
  "brand_preferences": {
    "milk": "Horizon Organic",
    "yogurt": "Chobani"
  },
  "dietary_restrictions": ["vegetarian"],
  "allergens": ["peanuts"],
  "favorite_items": [
    "mango",
    "strawberries",
    "hummus"
  ],
  "shopping_patterns": {
    "typical_days": ["Wednesday", "Sunday"],
    "typical_stores": ["Whole Foods", "Trader Joe's"],
    "avg_trip_frequency_days": 5,
    "preferred_time": "evening"
  }
}
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-26 | Francisco | Initial PRD based on discovery interview |

---

**Next Steps:**
1. Review and approve PRD
2. Create grocery tracker skill
3. Implement MVP in Python
4. Test with real grocery trips
5. Iterate based on feedback
