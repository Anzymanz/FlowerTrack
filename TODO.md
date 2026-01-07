# FlowerTrack todo list (fresh)

1) [x] Packaging & release hygiene
- Add a short CONTRIBUTING.md (dev setup, tests, build).
- Add a RELEASE.md with tag workflow + artifact notes.
- Consider Git LFS for binaries if you want to commit exe artifacts.

2) [x] Notification UX
- Add a "quiet hours" option for desktop/HA notifications.
- Add a summary-only mode vs full detail toggle.

3) [x] Scraper resilience
- Centralize retry/backoff config into a small class and expose in settings.
- Add explicit "last successful scrape" timestamp to UI.

4) [x] Config validation + migration
- Add explicit schema version bump and a migration log entry in config.
- Validate selectors and URL formats with inline UI hints.

5) [x] Test coverage
- Add unit tests for per-gram calculation formatting and price parsing edge cases.
- Add tests for empty-parse retry behavior and stop conditions.

6) [x] Performance cleanup
- Move repeated parser cache lookups to a small cache helper with TTL.
- Reduce duplicate make_identity_key calls in change detection.

7) [x] UI polish
- Add a lightweight status bar for scraper state + next run countdown.
- Align spacing in settings window grids (consistent padding).

8) [x] Repository hygiene
- Ensure `build/`, `dist/`, `__pycache__/` stay ignored.
- Remove legacy files that are no longer referenced.
