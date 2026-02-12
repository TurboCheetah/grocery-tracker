# Post-Merge Nitpick Follow-Ups Handoff (PR #23)

Date: 2026-02-12  
Branch: `codex/nitpick-followups`  
Merged PR: `#23` (`[codex] Add type-safe enums and tighten receipt/route nitpick fixes`)

## Scope

Post-merge review follow-ups after Sprint 6:

- Tightened receipt savings rendering for zero-quantity edge cases
- Reduced repeated data loads in route planning recommendation loop
- Added/strengthened regression coverage for formatter and route planner behavior
- Introduced type-safe enums and stricter validation for savings and route assignment sources

## Runtime/Model Changes

- `src/grocery_tracker/models.py`
  - Added `SavingsSource` enum
  - Added `RouteAssignmentSource` enum
  - Updated `SavingsRecord.source` to enum type
  - Added `Field(ge=0)` on `SavingsRecord.savings_amount`
  - Updated `RouteItemAssignment.assignment_source` to enum type
- `src/grocery_tracker/analytics.py`
  - Extended `recommend_item(...)` to accept optional preloaded `history` and `oos_records`
  - Updated `plan_shopping_route(...)` to preload once and pass through
- `src/grocery_tracker/output_formatter.py`
  - Preserved explicit zero quantity in inferred savings calculation (default only when quantity is missing)

## Tests Updated

- `tests/test_output_formatter.py`
  - Added inferred-savings rendering test
  - Added zero-quantity regression test
  - Strengthened zero-quantity assertion to check row-level dash rendering
- `tests/test_output_formatter_phase2.py`
  - Added empty-route renderer test
- `tests/test_analytics.py`
  - Added route planner data-load reuse regression test
- `tests/test_models.py`
  - Added negative savings validation test
- `tests/test_phase3_analytics.py`
  - Clarified brand preference normalization expectation in recipe payload constraints

## Validation

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .` (pass)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check src/` (pass)
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` (pass, `504 passed`, coverage `93.25%`)

## Linear Mapping / Status

All related issues are `Done`; PR #23 provides post-merge hardening updates touching:

- Sprint 3 route work: `TUR-12`, `TUR-13`, `TUR-14`
- Sprint 4 savings work: `TUR-16`, `TUR-17`
- Sprint 6 follow-up context: `TUR-20`, `TUR-21`

