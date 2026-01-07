# FlowerTrack todo list (next improvements)

1) [x] Config unification
- Merge tracker/scraper config into a single JSON with sections (tracker/scraper/ui) to prevent drift.
- Add a migration step that preserves existing `tracker_settings.json` + `scraper_config.json`.

2) [x] Scraper state helper
- Add centralized read/write/validate helpers for `scraper_state.json` (PID checks, stale cleanup).
- Use the helper in `ui_main.py` and `tracker_ui_helpers.py`.

3) [x] Tray icon consistency
- Centralize status->color logic in `tray.py` (or a new helper) and reuse for tracker + scraper.
- Ensure single tray icon ownership (tracker only) with consistent update calls.

4) Tracker modularization
- Split `ui_tracker.py` further: 
  - `tracker_ui.py` (widgets + layout)
  - `tracker_controller.py` (actions + state)
  - `tracker_storage.py` (load/save + migrations)
  - `tracker_tray.py` (tray behavior + status dots)

5) [x] Remove dead tracker settings
- Stop persisting `minimize_to_tray` / `close_to_tray` in tracker config.
- Migrate away legacy flags when loading.

6) Theme centralization
- Move dark/light palettes and titlebar helpers to a shared `ui_theme.py`.
- Remove duplicate theme logic in `ui_main.py`, `ui_tracker.py`, `flowerlibrary.py`.

7) Error/state machine for capture
- Implement a small state machine with explicit transitions (idle/running/retrying/faulted/stopped).
- Drive UI/tray updates from state transitions only.

8) Tests for parsing
- Add tests with HTML/text fixtures to lock THC/CBD/price parsing and per-gram calculations.
- Add regression tests for change detection (new/removed/price/stock).

9) Entry point cleanup
- Move launcher logic to `entrypoints.py` (optional).
- Keep `flowertracker.pyw` as the single entry point.

10) Cleanup tmp scripts
- Remove or move `tmp_script.py`/`tmp_script2.py` into `scripts/`.
