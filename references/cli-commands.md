# CLI Command Reference

Complete reference for all grocery-tracker CLI commands with options and response formats.

## Table of Contents

- [List Management](#list-management)
- [Receipt Processing](#receipt-processing)
- [Price Analytics](#price-analytics)
- [Spending Analytics](#spending-analytics)
- [Inventory Management](#inventory-management)
- [Waste Tracking](#waste-tracking)
- [Budget Management](#budget-management)
- [Out-of-Stock Tracking](#out-of-stock-tracking)
- [User Preferences](#user-preferences)

---

## List Management

### add

Add item to grocery list.

```bash
grocery add "bananas" \
  --quantity 3 \
  --store Giant \
  --category Produce \
  --unit count \
  --brand Dole \
  --price 0.49 \
  --priority high \
  --by Francisco \
  --notes "Get the ripe ones" \
  --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--quantity` | `-q` | Number of items (default: 1) |
| `--store` | `-s` | Store name |
| `--category` | `-c` | Category (Produce, Dairy & Eggs, etc.) |
| `--unit` | `-u` | Unit of measure |
| `--brand` | `-b` | Brand preference |
| `--price` | `-p` | Estimated price |
| `--priority` | | high, medium, or low (default: medium) |
| `--by` | | Who added the item |
| `--notes` | `-n` | Additional notes |
| `--force` | `-f` | Allow duplicate items |

**Response:**
```json
{
  "success": true,
  "data": {
    "item": {
      "id": "uuid",
      "name": "Bananas",
      "quantity": 3,
      "unit": "count",
      "category": "Produce",
      "store": "Giant",
      "brand_preference": "Dole",
      "estimated_price": 0.49,
      "priority": "high",
      "added_by": "Francisco",
      "added_at": "2026-01-26T10:30:00Z",
      "notes": "Get the ripe ones",
      "status": "to_buy"
    }
  }
}
```

### list

View grocery list with filtering.

```bash
grocery list --store Giant --by-store --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--store` | `-s` | Filter by store |
| `--category` | `-c` | Filter by category |
| `--status` | | Filter: to_buy, bought, still_needed |
| `--by-store` | | Group items by store |
| `--by-category` | | Group items by category |

**Response:**
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
          "brand_preference": "Dole",
          "estimated_price": 0.49,
          "priority": "high",
          "added_by": "Francisco",
          "notes": "Get ripe ones",
          "status": "to_buy"
        }
      ]
    }
  }
}
```

### update

Modify existing item.

```bash
grocery update <item-id> \
  --name "Organic Bananas" \
  --quantity 5 \
  --store "Whole Foods" \
  --priority high \
  --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--name` | | New item name |
| `--quantity` | `-q` | New quantity |
| `--store` | `-s` | New store |
| `--category` | `-c` | New category |
| `--unit` | `-u` | New unit |
| `--brand` | `-b` | New brand preference |
| `--price` | `-p` | New estimated price |
| `--priority` | | high/medium/low |
| `--notes` | `-n` | New notes |
| `--status` | | to_buy/bought/still_needed |

### remove

Remove item from list.

```bash
grocery remove <item-id> --json
```

### bought

Mark item as purchased.

```bash
grocery bought <item-id> --quantity 3 --price 1.47 --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--quantity` | `-q` | Actual quantity bought |
| `--price` | `-p` | Actual price paid |

### clear

Clear items from list.

```bash
grocery clear --bought --json  # Clear only bought items
grocery clear --all --json     # Clear all items
```

---

## Receipt Processing

### receipt process

Process receipt data and reconcile with list.

```bash
grocery receipt process --data '<json>' --json
grocery receipt process --file receipt.json --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--data` | `-d` | Receipt JSON string |
| `--file` | `-f` | Path to receipt JSON file |

**Input JSON structure:**
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
      "total_price": 1.47,
      "category": "Produce"
    }
  ],
  "subtotal": 1.47,
  "tax": 0.00,
  "total": 1.47,
  "payment_method": "Credit"
}
```

**Note:** `line_items[].category` is optional but recommended. The skill/LLM layer should populate it for better analytics.

**Response:**
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

### receipt list

List processed receipts.

```bash
grocery receipt list --json
```

---

## Price Analytics

### price history

View price history for an item.

```bash
grocery price history "milk" --store Giant --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--store` | `-s` | Filter by store |

**Response:**
```json
{
  "success": true,
  "data": {
    "item": "milk",
    "current_price": 5.99,
    "average_price": 5.74,
    "lowest_price": 5.29,
    "highest_price": 6.49,
    "price_points": [
      {"date": "2026-01-20", "price": 5.99, "store": "Giant"}
    ]
  }
}
```

---

## Spending Analytics

### stats

Spending summary.

```bash
grocery stats --period monthly --budget 500 --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--period` | `-p` | weekly, monthly, or yearly |
| `--budget` | `-b` | Budget for comparison |

**Response:**
```json
{
  "success": true,
  "data": {
    "spending": {
      "period": "monthly",
      "start_date": "2026-01-01",
      "end_date": "2026-01-31",
      "total_spending": 450.00,
      "receipt_count": 6,
      "item_count": 42,
      "categories": [
        {"category": "Produce", "total": 80.00, "percentage": 17.8, "item_count": 12},
        {"category": "Dairy & Eggs", "total": 65.00, "percentage": 14.4, "item_count": 9}
      ],
      "budget_limit": 500.00,
      "budget_remaining": 50.00,
      "budget_percentage": 90.0
    }
  }
}
```

### stats frequency

Purchase frequency analysis.

```bash
grocery stats frequency "milk" --json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "frequency": {
      "item_name": "milk",
      "category": "Dairy & Eggs",
      "average_days": 5.2,
      "last_purchased": "2026-01-23",
      "days_since": 4,
      "next_expected": "2026-01-28",
      "confidence": "high",
      "total_purchases": 8
    }
  }
}
```

### stats compare

Price comparison across stores.

```bash
grocery stats compare "milk" --json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "comparison": {
      "item_name": "milk",
      "stores": {
        "Giant": 5.99,
        "Trader Joe's": 4.99
      },
      "cheapest_store": "Trader Joe's",
      "cheapest_price": 4.99,
      "savings": 1.00
    }
  }
}
```

### stats bulk

Bulk buying analysis.

```bash
grocery stats bulk --days 90 --json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "bulk_buying": {
      "lookback_days": 90,
      "recommendations": [
        {
          "item_name": "Soda",
          "store": "Giant",
          "single_quantity": 1,
          "single_unit_price": 2.00,
          "bulk_quantity": 12,
          "bulk_unit_price": 1.50,
          "unit_savings": 0.50,
          "unit_savings_percent": 25.0,
          "estimated_monthly_quantity": 10.0,
          "estimated_monthly_savings": 5.00,
          "single_purchase_count": 3,
          "bulk_purchase_count": 2,
          "confidence": "medium"
        }
      ]
    }
  }
}
```

### stats suggest

Smart shopping suggestions.

```bash
grocery stats suggest --json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "type": "restock",
        "item_name": "milk",
        "priority": "high",
        "message": "Usually buy every 5 days, last purchase 6 days ago",
        "data": {"average_interval": 5, "days_since": 6}
      },
      {
        "type": "price_alert",
        "item_name": "eggs",
        "priority": "medium",
        "message": "Price at Giant is $5.00 (+20% vs avg $4.00)",
        "data": {"store": "Giant", "current_price": 5.00, "average_price": 4.00}
      }
    ]
  }
}
```

---

## Inventory Management

### inventory add

Add to household inventory.

```bash
grocery inventory add "milk" \
  --quantity 1 \
  --unit gallon \
  --category "Dairy & Eggs" \
  --location fridge \
  --expires 2026-01-28 \
  --threshold 1 \
  --by Francisco \
  --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--quantity` | `-q` | Amount |
| `--unit` | `-u` | Unit of measure |
| `--category` | `-c` | Category |
| `--location` | `-l` | pantry, fridge, or freezer |
| `--expires` | | Expiration date (YYYY-MM-DD) |
| `--threshold` | | Low stock alert threshold |
| `--by` | | Who added the item |

### inventory list

View inventory.

```bash
grocery inventory list --location fridge --category "Dairy & Eggs" --json
```

### inventory expiring

Items expiring soon.

```bash
grocery inventory expiring --days 3 --json
```

### inventory low-stock

Items below threshold.

```bash
grocery inventory low-stock --json
```

### inventory use

Consume inventory item.

```bash
grocery inventory use <item-id> --quantity 1 --json
```

### inventory remove

Remove from inventory.

```bash
grocery inventory remove <item-id> --json
```

---

## Waste Tracking

### waste log

Log wasted item.

```bash
grocery waste log "lettuce" \
  --quantity 1 \
  --unit head \
  --reason spoiled \
  --cost 3.99 \
  --by Francisco \
  --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--quantity` | `-q` | Amount wasted |
| `--unit` | `-u` | Unit of measure |
| `--reason` | `-r` | spoiled, never_used, overripe, other |
| `--cost` | | Estimated cost |
| `--by` | | Who logged |

### waste list

View waste records.

```bash
grocery waste list --item lettuce --reason spoiled --json
```

### waste summary

Waste analysis.

```bash
grocery waste summary --period monthly --json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "waste_summary": {
      "total_items_wasted": 8,
      "total_cost": 24.50,
      "by_reason": {"spoiled": {"count": 5, "cost": 18.00}},
      "insights": ["Lettuce spoils frequently - consider buying smaller quantities"]
    }
  }
}
```

---

## Budget Management

### budget set

Set monthly budget.

```bash
grocery budget set 500 --month 2026-01 --json
```

### budget status

Check budget status.

```bash
grocery budget status --month 2026-01 --json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "budget": {
      "month": "2026-01",
      "monthly_limit": 500.00,
      "spent": 450.00,
      "remaining": 50.00,
      "percentage_used": 90,
      "on_track": true
    }
  }
}
```

---

## Out-of-Stock Tracking

### out-of-stock report

Report item as out of stock.

```bash
grocery out-of-stock report "oat milk" "Trader Joe's" --sub "almond milk" --by Francisco --json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--sub` | `-s` | Substitution purchased |
| `--by` | | Who reported |

### out-of-stock list

View out-of-stock items.

```bash
grocery out-of-stock list --item "oat milk" --store "Trader Joe's" --json
```

---

## User Preferences

### preferences view

View user preferences.

```bash
grocery preferences view "Francisco" --json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "preferences": {
      "user": "Francisco",
      "brand_preferences": {"milk": "Organic Valley"},
      "dietary_restrictions": ["vegetarian"],
      "allergens": ["peanuts"],
      "favorite_items": ["avocados"]
    }
  }
}
```

### preferences set

Set user preferences.

```bash
grocery preferences set "Francisco" \
  --brand "milk:Organic Valley" \
  --dietary vegetarian \
  --allergen peanuts \
  --favorite avocados \
  --json
```

**Options (repeatable):**
| Option | Description |
|--------|-------------|
| `--brand` | "item:brand" format |
| `--dietary` | Dietary restriction |
| `--allergen` | Allergen to flag |
| `--favorite` | Favorite item |

---

## Error Responses

All commands may return errors:

```json
{
  "success": false,
  "error": "Error message",
  "error_code": "DUPLICATE_ITEM|NOT_FOUND|VALIDATION_ERROR"
}
```

| Code | Meaning | Action |
|------|---------|--------|
| `DUPLICATE_ITEM` | Item already exists | Offer to increase quantity or use --force |
| `NOT_FOUND` | Item ID not found | Verify ID or search by name |
| `VALIDATION_ERROR` | Invalid input data | Check required fields |
