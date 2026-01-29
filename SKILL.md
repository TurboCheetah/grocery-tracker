---
name: grocery-tracker
description: Grocery list and inventory management CLI. Use when users want to (1) add/remove/update items on grocery lists, (2) process receipt images to track purchases, (3) view shopping lists formatted for chat platforms, (4) analyze spending or price history, (5) manage household inventory with expiration tracking, (6) track food waste, (7) set/check budgets, (8) report out-of-stock items, (9) manage user preferences (brands, dietary, allergens), or (10) get smart shopping suggestions. Triggers on phrases like "add to list", "what's on my list", "process this receipt", "how much have I spent", "what's expiring", "log waste", "set budget".
---

# Grocery Tracker

Grocery list and household inventory management with receipt processing, analytics, and multi-store intelligence.

## Quick Reference

```bash
# List Management
grocery add "item" --quantity 3 --store Giant --json
grocery list --by-store --json
grocery update <id> --quantity 5 --json
grocery bought <id> --price 2.99 --json
grocery remove <id> --json
grocery clear --bought --json

# Receipt Processing
grocery receipt process --data '<json>' --json
grocery receipt list --json

# Analytics
grocery price history "milk" --json
grocery stats --period monthly --json
grocery stats frequency "milk" --json
grocery stats compare "milk" --json
grocery stats suggest --json

# Inventory
grocery inventory add "milk" --location fridge --expires 2026-01-28 --json
grocery inventory list --json
grocery inventory expiring --days 3 --json
grocery inventory low-stock --json
grocery inventory use <id> --quantity 1 --json

# Waste & Budget
grocery waste log "item" --reason spoiled --cost 3.99 --json
grocery waste summary --period monthly --json
grocery budget set 500 --month 2026-01 --json
grocery budget status --json

# Other
grocery out-of-stock report "item" "Store" --json
grocery preferences view "User" --json
grocery preferences set "User" --dietary vegetarian --json
```

**Always use `--json` flag** for programmatic consumption.

**Full command reference:** See [references/cli-commands.md](references/cli-commands.md) for all options and response formats.

## Receipt Processing Workflow

When user uploads a receipt image:

1. **Extract data with vision** - Parse store, date, items, prices
2. **Format as JSON:**
```json
{
  "store_name": "Giant Food",
  "transaction_date": "2026-01-25",
  "line_items": [
    {"item_name": "Bananas", "quantity": 3, "unit_price": 0.49, "total_price": 1.47}
  ],
  "total": 1.47
}
```
3. **Call CLI:** `grocery receipt process --data '<json>' --json`
4. **Present results:**
```
Matched from your list: Bananas, Milk
Still need: Eggs, Bread
```

**Extraction guidelines:**
- Normalize item names (proper capitalization)
- Remove store-specific codes/SKUs
- Infer quantities when not explicit
- Use null for missing optional fields

## Adding Items

Parse natural language like "Add 3 bananas from Giant" into:

```bash
grocery add "bananas" --quantity 3 --store Giant --json
```

**Handle duplicates:** If `DUPLICATE_ITEM` error, ask user:
1. Increase quantity
2. Add separate entry (use `--force`)
3. Keep existing

**If store not specified**, prompt user with store options.

## Viewing Lists

```bash
grocery list --json
```

Format output for the chat platform:

**Telegram (markdown):**
```markdown
# Grocery List

## Giant Food
### Produce
- **Bananas** (3)
- **Avocados** (2)
```

**Signal (plain):**
```
GROCERY LIST

GIANT FOOD
Produce:
- Bananas (3)
- Avocados (2)
```

Group by: Store > Category > Aisle (if available)

## Analytics Workflows

### Spending Summary
```bash
grocery stats --period monthly --json
```
Present: Total spent, budget remaining, category breakdown.

### Purchase Frequency
```bash
grocery stats frequency "milk" --json
```
Present: "You buy milk every ~5 days. Last: 6 days ago. Consider adding to list."

### Price Comparison
```bash
grocery stats compare "milk" --json
```
Present: Prices by store, cheapest option, potential savings.

### Smart Suggestions
```bash
grocery stats suggest --json
```
Present proactively when appropriate:
- Restock reminders based on purchase patterns
- Price alerts for increases
- Out-of-stock warnings

## Inventory Management

Track household inventory with expiration dates:

```bash
# Add to inventory
grocery inventory add "milk" --location fridge --expires 2026-01-28 --threshold 1 --json

# Check expiring items
grocery inventory expiring --days 3 --json

# Check low stock
grocery inventory low-stock --json

# Use items
grocery inventory use <id> --quantity 1 --json
```

**Locations:** pantry, fridge, freezer

Present expiring items as alerts: "Milk expires in 3 days (Jan 28)"

## Waste Tracking

Log and analyze food waste:

```bash
grocery waste log "lettuce" --reason spoiled --cost 3.99 --json
grocery waste summary --period monthly --json
```

**Reasons:** spoiled, never_used, overripe, other

Present insights: "Lettuce spoils frequently - consider buying smaller quantities"

## Budget Management

```bash
grocery budget set 500 --month 2026-01 --json
grocery budget status --json
```

Present: Budget, spent, remaining, percentage, on-track status.

## User Preferences

Store brand preferences, dietary restrictions, and allergens:

```bash
grocery preferences view "Alice" --json
grocery preferences set "Alice" --brand "milk:Organic Valley" --dietary vegetarian --json
```

Incorporate in responses: "Note: Alice prefers Organic Valley milk"

## Multi-User Context

Alice and Bob share the list:
- Different brand preferences (Alice: Organic Valley, Bob: Horizon)
- Dietary restrictions (Bob is vegetarian)
- Shopping patterns (Alice: Tue/Sat, Bob: Wed/Sun)

## Output Best Practices

1. **Always use `--json`** for CLI calls
2. **Parse JSON** before presenting to user
3. **Format naturally** - no raw JSON shown to users
4. **Use emoji sparingly** - Only for success/warning indicators
5. **Keep concise** - users are on mobile
6. **Group items** - by store, category, or status

## Error Handling

| Error Code | Action |
|------------|--------|
| `DUPLICATE_ITEM` | Offer: increase quantity, use --force, or ignore |
| `NOT_FOUND` | Verify item ID or search by name |
| `VALIDATION_ERROR` | Check required fields, re-extract if receipt |

For low-confidence receipt extraction, present items with confidence and ask for corrections.
