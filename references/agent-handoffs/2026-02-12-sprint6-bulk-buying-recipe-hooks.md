# Sprint 6 Bulk Buying + Recipe Hook Handoff (GT-601/602)

Date: 2026-02-12  
Branch: `codex/sprint-6-bulk-buying-recipe-hooks`

## Implemented

- GT-601 bulk buying value analysis with unit normalization, break-even guidance, and monthly savings projection
- GT-602 recipe/use-it-up payload hooks for external skill-layer recipe generation

## Runtime Files Updated

- `src/grocery_tracker/models.py`
  - Added `BulkPackOption`, `BulkBuyingAnalysis`
  - Added `RecipeHookItem`, `RecipeHookPayload`
- `src/grocery_tracker/analytics.py`
  - Added `bulk_buying_analysis(...)`
  - Added `recipe_use_it_up_payload(...)`
  - Added helpers:
    - `_normalize_unit(...)`
    - `_estimate_monthly_pack_usage(...)`
    - `_recipe_constraints(...)`
- `src/grocery_tracker/main.py`
  - Added `grocery stats bulk` command
  - Added `grocery inventory use-it-up-payload` command
- `src/grocery_tracker/output_formatter.py`
  - Added rich rendering for `bulk_buying_analysis`
  - Added rich rendering for `recipe_payload`
- `src/grocery_tracker/__init__.py`
  - Exported new Sprint 6 models

## Behavior Notes

- Bulk analysis handles incompatible/unknown units safely (`unit_mismatch` or `unknown_unit`) without crashing.
- Bulk analysis JSON includes break-even recommendation plus assumptions.
- Recipe payload contains:
  - prioritized expiring items (sorted by earliest expiration)
  - dietary/allergen constraints
  - additional preference context for external recipe generation
- No external API calls are made from Python.

## Tests Updated

- `tests/test_phase3_analytics.py`
  - Added bulk analysis tests (comparable and unit mismatch)
  - Added recipe payload priority + constraints test
- `tests/test_cli_phase3.py`
  - Added `inventory use-it-up-payload` JSON test
  - Added `stats bulk` JSON tests
- `tests/test_output_formatter_phase3.py`
  - Added rich render tests for bulk analysis and recipe payload
- `tests/test_models.py`
  - Added model tests for all new Sprint 6 models

## Validation Commands and Results

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .` (pass)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check src/` (pass)
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` (pass, `493 passed`, coverage `92.63%`)

## Linear Status

- `TUR-20` / `TUR-21`: implementation complete in this branch.
- Issue state/comment updates in Linear were not applied in this pass.
