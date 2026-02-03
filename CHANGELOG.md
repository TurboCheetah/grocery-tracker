# Changelog

All notable changes to Grocery Tracker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-03

### Added
- Coupon/sale tracking with deal lifecycle (add, list, redeem)
- Savings tracker with manual logging and summary analytics
- JSON + SQLite persistence for deals and savings records
- Rich/JSON output rendering for deals and savings

## [1.0.0] - 2026-01-30

### Added

#### Core Features
- Add, remove, update, and view grocery list items
- Mark items as bought with optional price and quantity tracking
- Duplicate detection with `--force` override
- Filter and group by store, category, or status
- Clear bought items or entire list

#### Receipt Processing
- Process structured receipt JSON data
- Automatic reconciliation with grocery list (bought vs still needed)
- Receipt storage and listing

#### Price & Analytics
- Price history tracking per item per store
- Spending analytics (weekly/monthly/yearly)
- Category breakdown with budget comparison
- Purchase frequency analysis with restock suggestions
- Multi-store price comparison
- Out-of-stock tracking with substitution history

#### Inventory Management
- Track household inventory with quantities
- Expiration date tracking with alerts
- Low stock detection
- Automatic inventory updates from receipts
- Storage location support (pantry, fridge, freezer, etc.)

#### Waste Tracking
- Log wasted items with reason and cost
- Waste reduction insights

#### Budgeting
- Monthly budget tracking with status
- Per-category budget limits
- Budget alerts at configurable thresholds

#### User Preferences
- Brand preferences per user
- Dietary restrictions tracking
- Allergen tracking
- Favorite items

#### Output Formats
- Rich terminal output with tables and panels
- JSON output mode (`--json`) for programmatic access

#### Data Storage
- JSON backend (default)
- SQLite backend (optional)
- Migration tool for JSON to SQLite
- TOML configuration with search paths

### Technical
- Python 3.12+
- uv package manager
- 426 tests, 95% coverage
