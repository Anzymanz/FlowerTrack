# Changelog

## 0.21
- Restock/out-of-stock transitions now set a stock delta so stock pills can show green/red changes consistently.
- Skipped applying partial API captures when pagination fails (prevents false removals).
- Centralized price/stock/restock/out-of-stock diff logic for reuse across UI and HA payloads.
- Logged config save failures to a config error log instead of silently ignoring them.
- Unified tracker config access in flowerlibrary and mixcalc to use config helpers instead of direct JSON reads.
- Added atomic writes for last-parse/change/scrape and scraper state files to reduce partial-write risk.
- Moved post-parse export/notification work off the UI thread and made UI logging thread-safe.
