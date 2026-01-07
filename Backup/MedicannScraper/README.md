# MedicannScraper (notes)

## Config layout
- Stored at `%APPDATA%/MedicannScraper/tracker_config.json` (schema versioned).
- Keys:
  - `version`: schema version integer.
  - `url`: target URL.
  - `username` / `password`: DPAPI-encrypted (prefixed `enc:`) when saved.
  - `username_selector` / `password_selector` / `login_button_selector`: CSS selectors.
  - `interval_seconds`: scrape interval.
  - `login_wait_seconds`: wait after login.
  - `post_nav_wait_seconds`: wait after navigation.
  - `timeout_ms`: Playwright timeout.
  - `headless`: launch headless.
  - `auto_notify_ha`: send HA webhook on changes.
  - `ha_webhook_url` / `ha_token`: webhook config (token encrypted on save).
  - `notify_price_changes`, `notify_stock_changes`, `notify_windows`: notification toggles.
  - `minimize_to_tray`, `close_to_tray`: tray behavior.
- Old configs are migrated on load; missing values are defaulted.
