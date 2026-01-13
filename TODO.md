# TODO

- [x] Add explicit shutdown/join for background threads and tray icon on exit to avoid lingering processes.
- Centralize tray quit/restore paths to avoid duplicated logic between tracker and scraper.
- Add guardrails for config file writes (atomic write + backup on failure).
- Move hard-coded UI dimensions into config defaults and restore last window positions on launch.
- Make stats panel optionally show CBD-only averages and totals when CBD tracking is enabled.
- Add a "recent exports" list with timestamps and open action in the scraper UI.
- Normalize log entry schema (ensure grams_used/grams/efficiency keys are always present).
- Add validation around mixed-stock creation (non-empty name, >0 grams, distinct sources).
- Add unit tests for tray quit path, mixed stock updates, and config migration defaults.
- Add a lightweight smoke test to ensure the exe boots and creates appdata folders.
