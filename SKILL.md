---
name: grocery-tracker
description: Comprehensive grocery list and inventory management system with receipt processing, price tracking, and shopping analytics. Use when users want to add/remove items from grocery lists, process receipt images for purchase tracking, view shopping lists in various formats (markdown/Telegram/Signal), analyze spending patterns, track price history, manage household inventory, or get smart shopping recommendations. Handles multi-store organization, shared household preferences, and budget tracking.
---

# Grocery Tracker

Intelligent grocery list and household inventory management with receipt processing, analytics, and multi-store intelligence.

## Core Capabilities

The grocery tracker CLI provides:
- List management (add, remove, view, mark as bought)
- Receipt processing via vision → structured data
- Price tracking and history
- Purchase frequency analysis
- Multi-store comparison
- Spending analytics and budgeting
- Inventory management
- Output in multiple formats (Rich terminal, JSON, markdown)

## Quick Reference: CLI Commands

```bash
# List Management
grocery add "bananas" --quantity 3 --store Giant --json
grocery list --json
grocery remove <item-id> --json
grocery bought <item-id> --json

# Receipt Processing
grocery receipt process --data '<json>' --json

# Analytics
grocery stats --json
grocery stats --item milk --json

# Inventory
grocery inventory add "milk" --quantity 1 --location fridge --json
grocery inventory view --json
```

**Critical:** Always use `--json` flag when invoking CLI for programmatic consumption.

## Receipt Processing Workflow

When a user uploads a receipt image, follow this workflow:

### Step 1: Extract Receipt Data Using Vision

Use your multimodal capabilities to analyze the receipt image and extract:

**Required fields:**
- `store_name` (string) — e.g., "Giant Food"
- `transaction_date` (YYYY-MM-DD) — e.g., "2026-01-25"
- `line_items` (array) — List of purchased items
- `total` (number) — Total amount spent

**Optional fields:**
- `store_location` (string) — e.g., "Rockville, MD"
- `transaction_time` (HH:MM) — e.g., "14:32"
- `subtotal` (number)
- `tax` (number)
- `payment_method` (string) — e.g., "Credit Card"

**Line item structure:**
```json
{
  "item_name": "string",     // Normalize capitalization
  "quantity": number,         // Default to 1 if not shown
  "unit_price": number,       // Per-item price
  "total_price": number       // Total for this line
}
```

### Step 2: Format as JSON

Create a properly formatted JSON object:

```json
{
  "store_name": "Giant Food",
  "store_location": "Rockville, MD",
  "transaction_date": "2026-01-25",
  "transaction_time": "14:32",
  "line_items": [
    {
      "item_name": "Bananas",
      "quantity": 3,
      "unit_price": 0.49,
      "total_price": 1.47
    },
    {
      "item_name": "Milk",
      "quantity": 1,
      "unit_price": 5.49,
      "total_price": 5.49
    }
  ],
  "subtotal": 6.96,
  "tax": 0.00,
  "total": 6.96,
  "payment_method": "Credit"
}
```

**Guidelines for extraction:**
- Normalize item names (proper capitalization)
- Remove store-specific codes/SKUs
- Infer quantities when not explicit
- Extract prices as numbers (no currency symbols)
- Use null for missing optional fields
- Aim for >90% accuracy

### Step 3: Invoke CLI

Call the CLI with the extracted JSON:

```bash
grocery receipt process --data '{"store_name":"Giant Food",...}' --json
```

**Important:** Escape quotes properly in the JSON string.

### Step 4: Process Results

The CLI returns:

```json
{
  "success": true,
  "data": {
    "receipt_id": "receipt-123",
    "matched_items": 2,
    "still_needed": ["eggs", "bread"],
    "newly_bought": ["bananas", "milk"],
    "total_spent": 6.96,
    "items_purchased": 2
  }
}
```

### Step 5: Present to User

Format the response naturally:

```
✓ Receipt processed from Giant Food ($6.96)

Matched from your list:
• Bananas (3)
• Milk (1 gallon)

Still need to buy:
• Eggs (12)
• Bread (1 loaf)
```

## Adding Items to List

### Natural Language Processing

When users say things like:
- "Add bananas to the list"
- "Need 3 avocados from Trader Joe's"
- "Put milk on the grocery list"

**Extract:**
- Item name
- Quantity (if specified)
- Store (if specified, otherwise prompt)
- Category (infer or ask)

### CLI Invocation

```bash
grocery add "bananas" --quantity 3 --store Giant --category Produce --json
```

**Response:**
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

### Store Prompt

If store not specified, prompt user:

```
Which store should I add bananas to?
1. Giant (most common for Produce)
2. Trader Joe's
3. Whole Foods
```

### Duplicate Handling

If CLI returns duplicate error:

```json
{
  "success": false,
  "error": "Item 'bananas' already exists on the list",
  "error_code": "DUPLICATE_ITEM"
}
```

Ask user:
```
Bananas are already on your list (3, Giant).
What would you like to do?
1. Increase quantity (make it 6)
2. Add separate entry (different store/brand)
3. Keep existing
```

## Viewing the Grocery List

### Output Format Selection

**Default behavior:** Use JSON for programmatic parsing, then format for chat platform.

```bash
grocery list --json
```

**Returns:**
```json
{
  "success": true,
  "data": {
    "list": {
      "version": "1.0",
      "last_updated": "2026-01-26T10:30:00Z",
      "items": [
        {
          "id": "uuid",
          "name": "Bananas",
          "quantity": 3,
          "unit": "count",
          "category": "Produce",
          "store": "Giant",
          "aisle": "1",
          "status": "to_buy"
        }
      ]
    }
  }
}
```

### Format for Chat Platform

Detect platform and format appropriately:

**Telegram (full markdown support):**
```markdown
# 🛒 Grocery List

## Giant Food

### Produce
• **Bananas** (3) — Aisle 1
• **Avocados** (2, ripe) — Aisle 1

### Dairy
• **Milk** (Organic Valley, 1 gallon) — Aisle 6

---
*Last updated: Jan 26, 10:30 AM*
```

**Signal (basic formatting):**
```
🛒 GROCERY LIST

GIANT FOOD

Produce:
• Bananas (3)
• Avocados (2, ripe)

Dairy:
• Milk (Organic Valley, 1 gallon)

Last updated: Jan 26, 10:30 AM
```

**Text-only (no formatting):**
```
GROCERY LIST (Jan 26, 2026)

GIANT FOOD
Produce:
- Bananas (3)
- Avocados (2, ripe)

Dairy:
- Milk (Organic Valley, 1 gallon)
```

### Organizing by Store and Category

Group items by:
1. Store first (Giant, Trader Joe's, Whole Foods)
2. Category within store (Produce, Dairy, Meat, etc.)
3. Optionally by aisle if available

This helps optimize shopping routes.

## Removing Items

```bash
grocery remove <item-id> --json
```

**Response:**
```json
{
  "success": true,
  "message": "Removed bananas from grocery list"
}
```

Present confirmation:
```
✓ Removed bananas from your list
```

## Marking Items as Bought

When user says "I bought the bananas":

```bash
grocery bought <item-id> --json
```

**Response:**
```json
{
  "success": true,
  "message": "Marked bananas as bought"
}
```

## Analytics and Insights

### Spending Analytics

```bash
grocery stats --json
```

**Returns:**
```json
{
  "success": true,
  "data": {
    "stats": {
      "current_month_spending": 450.00,
      "last_month_spending": 425.00,
      "budget": 500.00,
      "remaining": 50.00,
      "categories": {
        "Produce": 80.00,
        "Dairy": 65.00,
        "Meat": 120.00
      }
    }
  }
}
```

**Present as:**
```
📊 Spending Summary

This month: $450.00 / $500.00 budget
Remaining: $50.00 (10%)

By category:
• Produce: $80 (18%)
• Dairy: $65 (14%)
• Meat: $120 (27%)
```

### Item-Specific Analytics

```bash
grocery stats --item milk --json
```

**Returns price history, purchase frequency:**
```json
{
  "success": true,
  "data": {
    "item": "milk",
    "price_history": [
      {"date": "2026-01-15", "price": 5.49, "store": "Giant"},
      {"date": "2026-01-20", "price": 5.99, "store": "Giant"}
    ],
    "average_price": 5.74,
    "purchase_frequency_days": 5.2,
    "last_purchased": "2026-01-20"
  }
}
```

**Present as:**
```
📈 Milk Analytics

Recent prices:
• Jan 20: $5.99 @ Giant
• Jan 15: $5.49 @ Giant
Average: $5.74

Purchase pattern:
You buy milk every ~5 days
Last purchase: 6 days ago
→ Consider adding to list
```

### Smart Suggestions

When appropriate, proactively suggest:

```
💡 Smart Suggestions

• Milk: Usually buy every 5 days, last purchase 6 days ago
• Eggs: Price is 20% higher than last month ($4.99 vs $3.99)
• Strawberries: In season now, typically $1.50 cheaper in June
```

## Inventory Management

### Adding to Inventory

```bash
grocery inventory add "milk" --quantity 1 --location fridge --expires 2026-01-28 --json
```

### Viewing Inventory

```bash
grocery inventory view --json
```

### Expiring Soon Alerts

```bash
grocery inventory check --json
```

Returns items expiring within 3 days.

## Error Handling

### Common Errors

**Duplicate Item:**
```json
{
  "success": false,
  "error": "Item already exists",
  "error_code": "DUPLICATE_ITEM"
}
```
→ Prompt user for action (increase quantity, separate entry, ignore)

**Item Not Found:**
```json
{
  "success": false,
  "error": "Item not found",
  "error_code": "NOT_FOUND"
}
```
→ Confirm item ID or search by name

**Invalid Data:**
```json
{
  "success": false,
  "error": "Invalid receipt data: missing required field 'total'",
  "error_code": "VALIDATION_ERROR"
}
```
→ Re-extract receipt or ask user to manually provide

### Receipt Extraction Issues

If vision extraction has low confidence:
1. Extract what you can
2. Present to user with confidence levels
3. Ask for corrections: "I'm not sure about these items - can you verify?"

## Multi-User Context

Alice and Bob share the grocery list. Consider:
- Brand preferences differ (Alice: Organic Valley, Bob: Horizon)
- Dietary restrictions (Bob is vegetarian)
- Shopping patterns (Alice: Tue/Sat, Bob: Wed/Sun)

When relevant, incorporate user context:
```
Note: Bob prefers Horizon Organic for milk
Note: Alice usually shops on Saturdays
```

## Output Best Practices

1. **Always use `--json` flag** for programmatic CLI calls
2. **Parse JSON responses** before presenting to user
3. **Format naturally** for chat - no raw JSON shown
4. **Use emoji sparingly** - ✓ for success, ⚠️ for warnings, 📊 for analytics
5. **Keep responses concise** - users are on mobile
6. **Group related items** - by store, category, or status

## Example Complete Workflow

**User:** "@Clawdbot add bananas to the list"

**Agent:**
1. Parse: "add bananas"
2. Call: `grocery add "bananas" --json`
3. Receive: `{"success": true, "data": {"item": {...}}}`
4. Respond: "✓ Added **bananas** to your Giant list (Produce)"

**User:** [uploads receipt image]

**Agent:**
1. Analyze image with vision
2. Extract: store, date, items, prices
3. Format JSON
4. Call: `grocery receipt process --data '...' --json`
5. Parse response
6. Respond: 
   ```
   ✓ Receipt processed from Giant ($6.96)
   
   Matched: bananas, milk
   Still need: eggs, bread
   ```

**User:** "What's on my list?"

**Agent:**
1. Call: `grocery list --json`
2. Parse JSON
3. Detect chat platform (Telegram)
4. Format with markdown
5. Send formatted list

## Testing Your Implementations

The Python CLI includes comprehensive tests (90%+ coverage). When developing:
- Run: `uv run pytest` to validate all tests pass
- All CLI commands have 100% test coverage
- Receipt processing, list management, analytics all tested

If tests fail, review error messages and fix implementation before using in production.
