# FlowerTrack todo list (next improvements)

1) [x] Theme centralization
- Create ui_theme.py with shared palettes, ttk style setup, and titlebar helpers.
- Replace duplicated theme logic in ui_main.py, ui_tracker.py, flowerlibrary.py.

2) [x] Capture state machine
- Introduce explicit state transitions (idle/running/retrying/faulted/stopped) in capture flow.
- Drive tray/status-dot updates from state transitions only.

3) Scraper config UI polish
- Minimize/close to tray settings restored in tracker UI.
- Hide deprecated tray options in scraper settings (they're now no-ops).
- Ensure load/save config uses unified flowertrack_config.json consistently.

4) Export server reuse
- Share a single export server between tracker + scraper (avoid competing ports).
- Expose last-opened export URL in tracker status area.

5) Notifications cleanup
- Consolidate notification formatting into notification_service (remove duplicates).
- Add toggle for Windows notifications in tracker context (if desired).

6) Parser tests
- Add fixture tests for THC/CBD/price parsing + per-gram calculations.
- Add regression tests for change detection (new/removed/price/stock).

7) Cleanup build artifacts
- Consider moving build/dist outputs to a /builds folder or gitignored path.
- Remove stale spec/shortcut files if not needed.
