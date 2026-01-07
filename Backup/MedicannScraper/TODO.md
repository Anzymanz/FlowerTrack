High-level improvements to tackle next

- Logging: wrap a single logger service that fans out to UI, file, tray, and stdout with levels; remove ad-hoc `_log_console` calls in workers via a thread-safe queue to UI.
- Error handling: centralize Playwright install/launch recovery with clear states (idle/running/retrying/faulted); surface retries and hard failures to UI + tray color; add backoff for repeated empty parses.
- Config: add schema validation/defaulting on load (pydantic/dataclasses or manual) and migration step; ensure secrets are always DPAPI-encrypted when written; document config layout in README.
- Notifications: unify HA + Windows notification formatting in `notification_service`; add test endpoint for HA that reports detailed errors; allow desktop notifications to be disabled separately from HA.
- Exports: move HTML template to a separate file/string with placeholders; ensure icons/assets resolve from `assets/` even when frozen; add cleanup of exports older than N days.
- UI/UX: keep dark-mode colors in one theme map and apply to all widgets; normalize hover/active states across tabs; switch remaining classic Tk widgets to ttk for consistent theming.
- Tray: guard pystray availability at startup; prevent multiple tray icons; ensure “Show”/“Quit” menu also closes/hides settings windows cleanly.
- Capture: extract capture worker into a class with injected callbacks; isolate scheduling/backoff from parsing; ensure navigation waits follow config and include a refresh-before-capture step.
- Parser robustness: add unit/regression tests for price/THC/CBD parsing against sample HTML/text; normalize currency handling; verify per-gram price calculations for varying gram/ml sizes.
- Packaging: add a `build.md`/script that pins pyinstaller args, includes assets, ensures Playwright browser download on first run if missing, and notes requirements (`pystray`, `Pillow`, `win10toast`).
