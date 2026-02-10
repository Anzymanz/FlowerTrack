## Highlights
- Added refresh-token-aware capture and broader API dumps to keep scraping fast with fewer browser launches.
- Added brand filtering to flower browser.
- Added change history viewer to flower browser.
- Updated UI button visuals to look cleaner.
- Improved exports with faster loading, auto-load on scroll, and richer header stats.
- Unified backup import/export into a single zip workflow with CONFIRM overwrite and proper reload.

## Changes
- Added full API traffic dump option, consistent dumps across capture paths. Dumps are saved under AppData\Roaming\FlowerTrack\dumps.
- Scraper now captures refresh tokens during Playwright bootstrap, and refreshes access tokens before falling back to Playwright.
- Improved export performance with lazy-loaded images, load-more paging, smaller batch size, and auto-load on scroll / short pages.
- Added export history modal with search, CSV export, data embedding, and detail formatting.
- Added change-log retention and clear/trim actions.
- Fixed encryption of scraper credentials, now auto-migrate any plaintext values.
- Improved Playwright bootstrap on first run (auto-install, timeouts, backoff, cleaner logs).
- Added scrollable scraper settings.
- UI polish: reduced button padding, tightened slider spacing/alignment, basket now closes on backdrop click.
- Flower browser: page header now shows product counts by stock status plus last-updated timestamp.
- Mix calculator: shared theming and direct THC:CBD ratio inputs.
- Flower Library: fixed dark title bars, spinbox backgrounds, border crash. Added basic load/save tests.
- Fixed missing subprocess import.
