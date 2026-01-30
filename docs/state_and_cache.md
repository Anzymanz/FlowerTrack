# State, Config, and Cache Files

This app separates **configuration**, **state**, and **generated/cache** files. All are stored under `%APPDATA%\FlowerTrack`.

## Config (user settings)
- `flowertrack_config.json` (root): unified config containing:
  - `tracker` (usage/log UI settings)
  - `scraper` (scrape settings, selectors, notification toggles)
  - `ui` (window sizes, column widths, UI toggles)
  - `library` (flower library settings)

## State (runtime/progress)
- `data\scraper_state.json`: last scrape/change timestamps and scraper status.
- `data\last_parse.json`: most recent parsed items snapshot (for diffing/notifications).

## Generated / cache
- `Exports\export-*.html`: generated product pages.
- `data\api_latest.json`: most recent raw API payloads.
- `data\api_dump_*.json`: historical API payload dumps (when enabled).
- `data\api_endpoints_*.json`: endpoint summaries (when enabled).
- `data\page_dump_*.html`: HTML page dumps (when enabled).

## Logs
- `logs\config_migrations.log`: config migrations.
- `logs\config_errors.log`: config save/load errors.

## Notes
- Clearing cache should remove only generated/exported files and not the unified config.
- The app recreates missing directories on startup.
