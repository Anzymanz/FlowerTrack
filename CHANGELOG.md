# Changelog

## Unreleased

- Switched scraper to API-based capture with pagination and auth header reuse.
- Removed legacy text parsing and brand hint database tooling.
- Added stock pills for all items and cleaned product title/type display.
- Parsed irradiation type and origin country; display irradiation selectively and flags via flagcdn.
- Added manual export & open button in scraper settings.
- Fixed strain-type parsing when lines precede product headers.
- Added capture dump toggle and log output for debugging auto-capture text.
- Added organization selection in scraper login (with default selector) and settings UI.
- Added scroll-after-navigation passes for lazy-loaded products.
- Improved parser block termination and strain type fallback to restore missing icons.
- Manual parser now forces export even when no changes are detected.
- Fixed scraper config loading when new scroll settings are present.
- Added tray shutdown safety and centralized tray icon handling.
- Persisted scraper window geometry and added CBD stats in the stats panel.
- Added log normalization on load and mixed-stock name validation.
- Added test coverage for config migrations, mix validation, tray helpers, and smoke startup.
- Removed the recent exports list from the scraper UI.
