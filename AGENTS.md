# Agent Instructions

## Project Overview

Grocery Tracker is a Python CLI application for grocery list and inventory management. It integrates with Clawdbot (Claude in group chats) for intelligent shopping assistance. Receipt image analysis happens at the skill layer (LLM), not in Python—the CLI only processes structured JSON.

## Development Commands

```bash
# Setup
uv sync                    # Install dependencies
uv sync --all-extras       # Install with dev dependencies

# Testing (mandatory - 90%+ coverage required)
uv run pytest              # Run all tests
uv run pytest --cov        # Run with coverage
uv run pytest tests/test_list_manager.py -v  # Single test file

# Linting/Formatting
uv run ruff check src/     # Lint
uv run ruff format src/    # Format

# Run CLI
uv run grocery --help      # CLI help
```

## Architecture

### Dual Output Mode
Every CLI command must support two output modes:
- **Rich mode** (default): Beautiful terminal UI with tables, colors, panels for humans
- **JSON mode** (`--json` flag): Structured JSON for LLM/programmatic consumption

```bash
grocery list              # Rich table output
grocery list --json       # {"success": true, "data": {...}}
```

### Receipt Processing Flow
```
User uploads receipt → Skill extracts JSON via vision → CLI processes JSON
```
The Python CLI has **zero external API dependencies**—all multimodal work is done by the invoking LLM agent.

### Key Modules
- `main.py` - CLI entry point (Typer)
- `list_manager.py` - CRUD operations for items
- `receipt_processor.py` - Process JSON receipts from skill layer
- `output_formatter.py` - Rich/JSON output formatting
- `data_store.py` - JSON file persistence
- `config.py` - TOML configuration loading

### Data Models (Pydantic)
- `Item` - Shopping list item with id, name, quantity, store, category, status
- `ReceiptData` - Receipt with store, date, line_items, totals
- `LineItem` - Individual receipt item with name, quantity, prices

## Key Patterns

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
```

### CLI Command Pattern
```python
@app.command()
def add(item: str, quantity: float = 1.0):
    try:
        result = list_manager.add_item(item, quantity)
        formatter.success(f"Added {item}", result)
    except Exception as e:
        formatter.error(str(e))
        raise typer.Exit(code=1)
```

## Technology Constraints

**Required:**
- Python 3.12+
- uv for package management (not pip)
- TOML for configuration (not JSON)
- Pydantic for data validation
- pathlib for file operations
- pytest with 90%+ coverage

**Forbidden:**
- No Anthropic API calls from Python (handled at skill layer)
- No Rich output when `--json` flag is set

## Testing Requirements

- 90%+ coverage on core logic
- 100% coverage on CLI commands
- All integration tests passing
- Use `typer.testing.CliRunner` for CLI tests
- Use `tmp_path` fixture for data persistence tests
