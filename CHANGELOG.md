# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `import_training_program` MCP tool — import public training library workouts and plans into your account ([#22](https://github.com/cygnusb/coros-mcp/issues/22))
  - Supports both single workouts (`/training/program/copy`) and multi-week plans (`/training/plan/copy`)
  - Uses `linked_id` from `get_training_library` results (not `program_id`)
  - `region_id` parameter: 1=CN, 2=US, 3=EU
  - Category validation rejects unknown types
  - Auto-reauth support via `_run_with_auth`

### Fixed
- `get_training_library` — fixed URL construction bug that hit `/training/training/api/...` (404) instead of correct root-domain path
- `get_training_library` — added pagination (offset/limit loop); was returning only 6 programs, now returns 198

### Changed
- `get_daily_metrics` merged into `get_training_analysis` — single tool now returns all 13 dashboard panels (daily records, week summaries, records, sport statistics, TL intensity, etc.) instead of requiring two tools that each called `/analyse/query` separately
  - `fetch_daily_records` renamed to `fetch_training_analysis` in `coros_api.py`
  - Documentation updated in README.md, CLAUDE.md, and source comments

### Removed
- `get_daily_metrics` MCP tool (superseded by merged `get_training_analysis`)
- Old `fetch_training_analysis` in `coros_api.py` (replaced by merged version)

## [Initial] — 2026-05-22

Forked from [cygnusb/coros-mcp](https://github.com/cygnusb/coros-mcp) (MIT License).

22 MCP tools for Coros Training Hub data: authentication, dashboard, training analysis, sleep, activities, workouts, training library, and more.
