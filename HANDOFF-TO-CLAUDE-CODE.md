# Grocery Tracker — Handoff to Claude Code

## Project Overview

Build a comprehensive grocery list and inventory management system in Python. The system integrates with Clawdbot (a Claude instance in group chats) to provide intelligent shopping assistance with receipt processing, price tracking, and analytics.

## Key Architecture Decisions

### 1. Receipt Processing at Skill Layer ✅

**Critical:** Receipt image analysis happens **at the skill layer**, not in Python.

**Flow:**
```
User uploads receipt → Skill uses vision to extract JSON → Python CLI processes JSON
```

**Why:**
- Clean separation: Skill handles multimodal, Python handles data
- No API dependencies in Python
- Faster execution (no API calls)
- Easier testing (no API mocks)

### 2. Dual Output Modes

Python CLI must support two output modes:

**Rich mode (default):**
- Beautiful terminal UI with tables, colors, panels
- For human developers running commands manually
- Uses `rich` library

**JSON mode (--json flag):**
- Structured JSON output
- For LLM/programmatic consumption
- Used by Clawdbot when invoking CLI

**Example:**
```bash
grocery list              # Rich table output
grocery list --json       # {"success": true, "data": {...}}
```

### 3. Modern Python Tooling

**Use uv for everything:**
- Package management (10-100x faster than pip)
- Dependency resolution
- Virtual environment management

**Use pyproject.toml:**
- All configuration in one place
- TOML for user config (not JSON)
- Python 3.12+ features

### 4. Testing is Mandatory

**Requirements:**
- 90%+ coverage on core logic
- 100% coverage on CLI commands
- All integration tests passing

**Why critical:**
- Enables autonomous validation
- Prevents regressions
- Documents expected behavior

## Documents Provided

1. **grocery-tracker-prd-v3.md** (68KB)
   - Complete product requirements
   - All features Phase 1-3
   - Data models
   - Example code
   - Testing requirements

2. **grocery-tracker-changelog-v3.md** (5KB)
   - Summary of architecture changes
   - Comparison old vs new approach
   - Quick reference

3. **grocery-tracker.skill** (packaged skill file)
   - Instructions for LLM agent
   - Receipt extraction workflow
   - CLI invocation patterns
   - Error handling

## Project Structure

```
grocery-tracker/
├── src/
│   └── grocery_tracker/           # Main package
│       ├── __init__.py
│       ├── main.py                # CLI entry (Typer)
│       ├── config.py              # TOML config loading
│       ├── list_manager.py        # CRUD operations
│       ├── receipt_processor.py   # Process JSON receipts
│       ├── analytics.py           # Stats, trends, insights
│       ├── inventory_manager.py   # Inventory tracking
│       ├── data_store.py          # JSON persistence
│       └── output_formatter.py    # Rich/JSON formatting
├── tests/
│   ├── conftest.py                # Fixtures
│   ├── test_list_manager.py
│   ├── test_receipt_processor.py
│   ├── test_data_persistence.py
│   ├── test_cli.py
│   └── test_integration.py
├── pyproject.toml                 # Project + dependencies
├── config.toml.example            # Example config
├── README.md
└── uv.lock                        # Lock file
```

## MVP Scope (Phase 1)

Focus on these features first:

### Must-Have
1. **List Management**
   - Add items (with quantity, store, category)
   - Remove items
   - View list (Rich + JSON)
   - Mark as bought

2. **Receipt Processing**
   - Accept structured JSON from skill
   - Match purchased items with list
   - Update "bought" vs "still needed"
   - Save receipt data

3. **Basic Organization**
   - Group by store
   - Group by category
   - Track status (to_buy, bought, still_needed)

4. **Dual Output**
   - Rich terminal UI for humans
   - JSON output for LLMs

5. **Data Persistence**
   - Save/load from JSON files
   - No SQLite yet (future Phase 2)

### Nice-to-Have (Phase 2+)
- Price tracking
- Purchase frequency analysis
- Spending analytics
- Inventory management
- Smart suggestions

## Key Data Models

### Item (List)
```python
from pydantic import BaseModel

class Item(BaseModel):
    id: str  # UUID
    name: str
    quantity: float
    unit: str | None
    category: str
    store: str
    aisle: str | None
    brand_preference: str | None
    estimated_price: float | None
    priority: str  # high, medium, low
    added_by: str  # Alice, Bob
    added_at: str  # ISO8601
    notes: str | None
    status: str  # to_buy, bought, still_needed
```

### Receipt
```python
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
```

## CLI Commands to Implement

### List Management
```bash
grocery add "bananas" --quantity 3 --store Giant --category Produce [--json]
grocery list [--store STORE] [--category CAT] [--json]
grocery remove ITEM_ID [--json]
grocery bought ITEM_ID [--quantity QTY] [--json]
```

### Receipt Processing
```bash
grocery receipt process --data '{"store_name":...}' [--json]
grocery receipt process --file receipt.json [--json]
```

### Analytics (MVP can be basic)
```bash
grocery stats [--json]
grocery stats --item ITEM [--json]
```

## Configuration Structure

**config.toml:**
```toml
[data]
storage_dir = "~/grocery-tracker/data"
backup_enabled = true

[defaults]
store = "Giant"
category = "Other"

[budget]
monthly_limit = 500.00

[users.alice]
dietary_restrictions = []
favorite_stores = ["Giant", "Trader Joe's"]

[users.bob]
dietary_restrictions = ["vegetarian"]
```

## Testing Strategy

### Unit Tests
Test each module independently:
- `test_list_manager.py` - Add/remove/get items
- `test_receipt_processor.py` - Process receipt JSON
- `test_data_persistence.py` - Save/load operations
- `test_output_formatter.py` - Rich/JSON formatting

### CLI Tests
Test every command:
```python
from typer.testing import CliRunner

def test_add_item_json():
    result = runner.invoke(app, [
        "add", "Bananas",
        "--quantity", "3",
        "--json"
    ])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output['success'] == True
```

### Integration Tests
Test complete workflows:
- Add items → process receipt → reconcile list
- Add items → view in different formats
- Receipt processing → price history update

## Development Workflow

```bash
# Setup
uv sync

# Run tests (do this often!)
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test
uv run pytest tests/test_list_manager.py -v

# Run CLI in dev
uv run grocery --help

# Lint/format
uv run ruff check src/
uv run ruff format src/
```

## Success Criteria

Before considering MVP complete:

- ✅ All CLI commands work with both Rich and JSON output
- ✅ Receipt processing correctly matches items
- ✅ List reconciliation (bought vs still needed) works
- ✅ Data persists correctly to JSON files
- ✅ Tests pass: 90%+ coverage, all integration tests green
- ✅ Config loads from TOML correctly
- ✅ Error handling returns proper JSON error responses

## Common Patterns

### Output Formatter Pattern
```python
class OutputFormatter:
    def __init__(self, json_mode: bool):
        self.json_mode = json_mode
    
    def output(self, data: dict, message: str = ""):
        if self.json_mode:
            print(json.dumps(data))
        else:
            # Rich formatting
            console.print(...)
    
    def error(self, message: str):
        if self.json_mode:
            print(json.dumps({"error": message, "success": False}))
        else:
            console.print(f"[red]✗[/red] {message}")
```

### CLI Command Pattern
```python
@app.command()
def add(
    item: str,
    quantity: float = 1.0,
    store: str = None,
    category: str = None,
):
    try:
        result = list_manager.add_item(item, quantity, store, category)
        formatter.success(f"Added {item}", result)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)
```

### Receipt Processing Pattern
```python
def process_receipt(self, receipt_data: ReceiptData) -> dict:
    # Save receipt
    receipt_id = self.data_store.save_receipt(receipt_data)
    
    # Match with list
    matched, still_needed = self._reconcile_list(receipt_data.line_items)
    
    # Update price history
    for item in receipt_data.line_items:
        self._update_price_history(item, receipt_data.store_name)
    
    return {
        "receipt_id": receipt_id,
        "matched_items": len(matched),
        "still_needed": still_needed,
        "total_spent": receipt_data.total
    }
```

## Important Notes

### What NOT to Do
- ❌ Don't call Anthropic API from Python
- ❌ Don't use pip (use uv)
- ❌ Don't use JSON for config (use TOML)
- ❌ Don't skip tests
- ❌ Don't output Rich formatting when --json flag is set

### What TO Do
- ✅ Use Pydantic for data validation
- ✅ Use pathlib for file operations
- ✅ Use proper typing (Python 3.12+)
- ✅ Test every function
- ✅ Handle errors gracefully
- ✅ Return proper JSON responses

## Questions to Consider

As you develop, think about:

1. **Item matching:** How fuzzy should name matching be? ("Milk" vs "WHOLE MILK")
2. **Duplicate prevention:** Store same item, different stores?
3. **Quantity tracking:** Handle partial purchases? (bought 2 of 3)
4. **Price updates:** Update estimated price after each purchase?
5. **List organization:** Default store preference per user?

Document your decisions in code comments.

## Resources

All documentation is in the PRD. Key sections:

- **Data Models:** Pages 15-20
- **CLI Commands:** Pages 35-40
- **Testing Requirements:** Pages 50-55
- **Configuration:** Pages 25-30
- **Receipt Processing:** Pages 45-50

## Ready to Start

You have everything needed:
1. Complete PRD with all requirements
2. Skill file showing how it will be used
3. This handoff document
4. Clear MVP scope

**Suggested first steps:**
1. Initialize project with uv
2. Set up pyproject.toml
3. Create basic project structure
4. Implement Item and ReceiptData models
5. Build list_manager with tests
6. Add CLI layer with Typer
7. Implement output formatter
8. Build receipt processor
9. Add data persistence
10. Complete integration tests

Good luck! The architecture is clean, the requirements are clear, and the tests will guide you.
