## Highlights
- Switched the Flower Browser to a fixed /flowerbrowser URL that always serves the latest export.
- Added live update prompts and tighter export refresh logic for faster, cleaner browsing.
- Improved basket reliability and auto-load/filters in the export UI.
- Polished tracker/scraper settings layout and usability.

## Changes
- Serve a fixed /flowerbrowser URL and keep only the latest export HTML after each successful scrape.
- Add a live update banner via SSE; prevent false refresh prompts with timestamp alignment and baseline handling.
- Only regenerate exports when changes are detected (regardless of notification settings).
- Improve export UI behavior: auto-load reliability, filter reset behavior, and history modal scroll locking.
- Persist basket contents across refreshes and harden remove/hover handling (including apostrophes/Unicode).
- Tweak stock handling: low-stock threshold < 15 and show "15+" when API maxes out at 15.
- Fix Balance oil titles showing as null and rename export title to "Available Products."
- Tracker/scraper settings polish: new Tracker/RoA sections, headless alignment, remove auto-open export option.
- Improve change history viewer layout and detail formatting.
- Bundle mix_utils in frozen builds and refresh documentation screenshots.
- Rename CBD toggle to "Track CBD flower" and exclude CBD stock from days-left when disabled.
