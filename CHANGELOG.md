# Changelog

## Unreleased
- Added retry policy settings (retry wait/backoff) and validation for the scraper.
- Added last successful scrape tracking and persistence.
- Added config migration logging and inline scraper setting hints.
- Added test coverage for parsing, per-gram prices, retry/backoff, and empty-stop behavior.
- Removed unused JSON export helper and cleaned imports.
- Renamed main entry to `flowertracker.py` and updated build line.
