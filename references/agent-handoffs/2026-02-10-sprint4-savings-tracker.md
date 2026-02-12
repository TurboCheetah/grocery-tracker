# Sprint 4 Completion Handoff (GT-401/402/403)

Date: 2026-02-10  
Branch: `codex/sprint-4-savings-tracker`

## Implemented

- GT-401 receipt sale/coupon metadata support
- GT-402 persisted savings records + savings aggregation
- GT-403 CLI savings command (`grocery stats savings`)

## Runtime Files Updated

- `src/grocery_tracker/models.py`
  - Extended `LineItem` and `Receipt` with discount/sale metadata
  - Added `SavingsRecord`, `SavingsContributor`, `SavingsSummary`
- `src/grocery_tracker/receipt_processor.py`
  - Accepts discount metadata and receipt-level discount aliases
  - Persists deterministic line-item and prorated receipt-level savings records
  - Marks price history entries as sale when discount metadata indicates sale pricing
- `src/grocery_tracker/data_store.py`
  - Added JSON persistence methods for savings records
- `src/grocery_tracker/sqlite_store.py`
  - Added `savings_records` table and CRUD methods
  - Added backward-compatible receipt/receipt-item discount columns for existing DBs
- `src/grocery_tracker/analytics.py`
  - Added `savings_summary(period=...)` with top item/store/category/source breakdowns
- `src/grocery_tracker/main.py`
  - Added `grocery stats savings --period ...`
- `src/grocery_tracker/output_formatter.py`
  - Added rich savings summary renderer
  - Enhanced receipt rendering to show discount/coupon totals and per-line savings
- `src/grocery_tracker/__init__.py`
  - Exported new savings models

## Tests Updated

- `tests/test_receipt_processor.py`
- `tests/test_data_store.py`
- `tests/test_sqlite_store.py`
- `tests/test_analytics.py`
- `tests/test_cli_phase2.py`
- `tests/test_output_formatter_phase2.py`
- `tests/test_models.py`

## Validation Commands and Results

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .` (pass)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check src/` (pass)
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` (pass, `475 passed`, coverage `94.21%`)

## Notes

- Savings persistence uses two deterministic sources:
  - `line_item_discount`: explicit line-level discount/coupon or inferred regular-vs-paid unit price
  - `receipt_discount`: prorated allocation of receipt-level discount/coupon totals by line-item totals
- Receipt parsing remains backward compatible with existing payloads; discount fields are optional.
- SQLite startup includes schema guardrails that add new receipt/receipt-item discount columns when missing.

## Linear Updates Completed

Set to `Done` and commented with implementation/validation notes:

- `TUR-15` (GT-401)
- `TUR-16` (GT-402)
- `TUR-17` (GT-403)

## Next Suggested Work

Start Sprint 5:

1. GT-501 seasonal purchase pattern model (`TUR-18`)
2. GT-502 seasonal price context and optimization suggestions (`TUR-19`)
