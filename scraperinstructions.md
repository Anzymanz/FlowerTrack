# FlowerTrack Scraper Rebuild Specification

This document is a complete functional spec for rebuilding the scraper subsystem.
It covers runtime architecture, control flow, auth bootstrapping, credential/token storage, failure behavior, notifications, and integration points.

Use this as the contract for parity.

---

## 1) Scraper Subsystem Purpose

The scraper is responsible for:

1. Capturing the Medicann product catalog (API-first).
2. Parsing and normalizing products.
3. Computing changes versus previous catalog.
4. Triggering notifications.
5. Persisting latest parse, unread changes, and change history.
6. Regenerating the browser export.

The scraper must be controllable from:
- its own scraper window UI,
- the tracker status indicator (start/stop commands),
- host/client mode constraints.

---

## 2) Key Modules and Roles

- `ui_scraper.py`
  - Scraper window UI, controls, settings, status text, progress bar.
  - Starts/stops capture worker.
  - Applies parse/diff/notify/persist stages.
  - Handles external command file (`start`, `stop`, `show`).

- `capture.py`
  - `CaptureWorker` orchestration.
  - API-first capture loop.
  - Auth cache validation/refresh/bootstrap.
  - Playwright/browser fallback path.
  - Retry/backoff behavior and pagination completeness checks.

- `parser.py`
  - Converts raw API payload into normalized items.
  - Applies product/type/name/stock/value extraction.

- `diff_engine.py`
  - Computes changes vs previous parse.

- `unread_changes.py`
  - Accumulates change highlights across scrapes until browser ack.

- `notifications.py`
  - Windows and Home Assistant notification sends.

- `config.py`
  - Unified scraper config schema/defaults.
  - Validation and typed coercion.
  - Secret encryption/decryption handling.

- `scraper_state.py`
  - Shared status markers (`status`, `pid`, `last_change`, `last_scrape`).

---

## 3) Runtime State and Lifecycle

### 3.1 Scraper statuses

Worker status state machine:
- `idle`
- `running`
- `retrying`
- `faulted`
- `stopped`

Valid transitions are strict. Invalid transitions are ignored and logged.

### 3.2 Start flow (`start_auto_capture`)

1. Persist current scraper settings.
2. Validate required target URL.
3. Clear stop event.
4. Reset runtime error counters and bootstrap prompt guard.
5. Write scraper shared state to `running`.
6. Build capture callbacks (`capture_log`, `apply_text`, `on_status`, `responsive_wait`, `stop_event`, manual-login prompt callback).
7. Start worker thread.

### 3.3 Stop flow (`stop_auto_capture`)

1. Set stop event.
2. Log stopped state.
3. Clear pagination UI busy indicator.
4. Update tray/status visuals.
5. Write scraper shared state to `stopped`.

Stop must be cooperative and safe during:
- waits,
- pagination loops,
- auth bootstrap waits.

---

## 4) Configuration Contract (Scraper)

The scraper settings contract includes:

- URL + selectors:
  - `url`
  - `username_selector`
  - `password_selector`
  - `login_button_selector`
  - `organization_selector`
- Credentials:
  - `username`
  - `password`
  - `organization`
- Timing/retry:
  - `interval_seconds`
  - `login_wait_seconds`
  - `post_nav_wait_seconds`
  - `retry_attempts`
  - `retry_wait_seconds`
  - `retry_backoff_max`
  - `timeout_ms`
- Capture mode:
  - `api_only` (primary mode)
  - `headless`
- Dump controls:
  - `dump_capture_html`
  - `dump_html_keep_files`
  - `dump_api_json` (full API traffic dump toggle)
  - `dump_api_keep_files`
- Filters:
  - `include_inactive`
  - `requestable_only`
  - `in_stock_only`
  - `filter_flower`
  - `filter_oil`
  - `filter_vape`
  - `filter_pastille`
- Notifications:
  - `notify_price_changes`
  - `notify_stock_changes`
  - `notify_out_of_stock`
  - `notify_restock`
  - `notify_new_items`
  - `notify_removed_items`
  - `notify_windows`
  - `auto_notify_ha`
  - `ha_webhook_url`
  - `ha_token`
  - `notification_detail`
  - `quiet_hours_enabled`
  - `quiet_hours_start`
  - `quiet_hours_end`
  - `quiet_hours_interval_seconds`
  - `notifications_muted`
  - `notification_restore_snapshot`
- Window behavior:
  - `show_log_window`
  - `log_window_hidden_height`
  - `window_geometry`
  - `settings_geometry`
  - `history_window_geometry`
  - `minimize_to_tray`
  - `close_to_tray`

Config read/write must be validated and coerced through schema rules before use.

---

## 5) Credential and Token Storage

### 5.1 Settings credentials

Scraper settings secrets are persisted encrypted:
- `username`
- `password`
- `ha_token`

Encryption/decryption is performed by config layer (`encrypt_secret`/`decrypt_secret` path via unified config I/O).

### 5.2 API auth cache

Auth bootstrap and API capture use a separate auth cache file:
- `data/api_auth.json`

Stored fields (logical):
- bearer access token
- refresh token
- `patient_id`
- `pharmacy_id`
- API host (`rpc_host`)
- optional user-agent
- capture timestamp

`token` and `refresh_token` must be encrypted at rest in this file.

### 5.3 Auth cache clear

Manual clear action is available in scraper maintenance.
Clear operation is blocked while auto-capture thread is active.

---

## 6) Capture Execution Model

### 6.1 API-first loop (default)

The worker loop in API mode does:

1. Set status `running` and log `API capture running...`.
2. Try direct API capture using cached auth.
3. If auth invalid/missing or no usable data:
   - attempt auth refresh and/or bootstrap depending on failure class.
4. If payloads obtained:
   - persist auth cache updates,
   - optionally write `api_latest.json`,
   - optionally write dump files,
   - call `apply_text("")` to hand off to parse pipeline.
5. If payloads not obtained:
   - set status `retrying` and wait using retry/backoff policy.
6. Sleep for interval via responsive wait, respecting stop event.

### 6.2 Non-API mode fallback

If `api_only` is false, legacy Playwright page+response capture path runs:
- performs login/navigation,
- captures response payloads from network events,
- includes HTTP fallback pagination reads when needed.

---

## 7) Direct API Capture Logic

### 7.1 Pre-flight

Requires valid auth cache values:
- token not expired (`exp - 60s` safety window),
- `rpc_host`,
- `patient_id`,
- `pharmacy_id`.

If token expired:
- attempt refresh via `auth/initialize` using refresh token.

### 7.2 Request composition

Base endpoint:
- `formulary-products` with query containing `take=50&skip=0` and selected filters.

Count endpoint:
- `formulary-products/count` derived from base URL query (without skip/take).

### 7.3 Pagination

Rules:
- fixed `take=50`
- loop `skip` from 50 to total-1 in steps of 50
- every page request includes auth headers
- stop request immediately aborts and returns failure (no parse)

### 7.4 Completeness protections

Capture must fail-safe (return `None`) if any of:

- count unavailable while first page is full,
- pagination request hard error,
- pagination interrupted by stop event,
- number of pages fetched < expected page count,
- total records fetched < expected total.

This explicitly prevents partial datasets from being parsed and persisted.

---

## 8) Auth Bootstrapping

### 8.1 Trigger conditions

Bootstrap is attempted when:
- auth cache missing/expired and direct capture fails, or
- API returns auth failures, or
- repeated empty API captures suggest stale auth context.

### 8.2 Manual vs automated bootstrap

- **Automated bootstrap**: uses saved username/password/organization.
- **Manual bootstrap**: if any credential/org field missing.
  - force visible browser (`headless = false`)
  - show user prompt once per session
  - wait for user login completion

### 8.3 Bootstrap capture strategy

During bootstrap browser session:
- subscribe to request/response events,
- collect request headers and auth initialize responses,
- periodically probe local/session storage for token-like values,
- derive patient/pharmacy context from API query or JWT claims.

### 8.4 Bootstrap wait behavior

- Automated timeout: ~35s.
- Manual timeout: ~90s.
- Poll every 0.5s with stop-event checks.
- Storage probe every ~2s.
- Optional one-time post-login navigation retry in automated mode.

On success:
- persist auth cache.
On failure:
- log bootstrap failure and use backoff before retry.

---

## 9) Failure Flows and Recovery

### 9.1 Auth failures

Symptoms:
- 401/403 responses,
- missing/expired token.

Recovery chain:
1. refresh token attempt,
2. bootstrap with Playwright,
3. backoff if bootstrap fails repeatedly.

### 9.2 Empty capture failures

If parsed product list is empty:
- trigger short retry path,
- increment error counters,
- stop auto-capture after threshold of repeated empty/fault cycles.

### 9.3 Pagination failures

Any failed/missing page causes:
- parse skipped,
- no diff/notifications/history write,
- next retry interval.

### 9.4 Playwright missing/browser missing

Recovery:
- invoke browser install callback,
- retry launch once after install.

If still unavailable:
- status `faulted` (or retrying in API path),
- clear log message.

### 9.5 Stop requested mid-cycle

If stop event is set before apply/parse:
- discard fetched payloads,
- transition to stopped cleanly.

---

## 10) Parse/Diff/Notify/Persist Pipeline (UI Side)

After capture worker emits `apply_text`:

1. **Parse stage**
   - load latest API dump/latest payload
   - parse to normalized items
   - dedupe by identity keys
   - apply scraper filter toggles
2. **Diff stage**
   - compare with previous parse
   - if no previous parse: seed baseline and suppress “all new” spam
3. **Notify stage**
   - honor per-category toggles
   - honor quiet-hours
   - honor muted state
   - optionally send Windows and HA notifications
4. **Persist stage**
   - save `last_parse`
   - append change history entry
   - merge unread changes accumulator
   - regenerate browser export
   - update last-change/last-scrape markers in scraper state

Baseline behavior:
- first successful capture logs baseline established and skips standard change notifications.

---

## 11) Notification Pipeline

Notification payload generation includes:
- change counts and summary text
- optional richer detail depending on `notification_detail`

Delivery channels:
- Windows desktop notifications (toggleable)
- Home Assistant webhook (toggleable)

Quiet hours behavior:
- if active, skip outbound notifications.

Mute behavior:
- store snapshot of notify flags before mute
- disable all notify channels while muted
- restore snapshot on unmute.

---

## 12) Dumping and Retention

### 12.1 API dump

When enabled:
- write full API payload dump file (`api_dump_*.json`)
- include both bootstrap and API pagination payloads where relevant.

Retention:
- keep newest `dump_api_keep_files`
- prune stale files by mtime.

### 12.2 HTML dump

When enabled:
- write captured page HTML dumps (`page_dump_*.html`)

Retention:
- keep newest `dump_html_keep_files`
- prune stale files.

---

## 13) External Command Channel

Control file:
- `data/scraper_command.json`

Supported commands:
- `start`
- `stop`
- `show`

Behavior:
- poll file periodically,
- process only monotonic newer timestamps,
- delete command file after consume,
- queue start command if capture still stopping.

This is how tracker status indicator controls scraper without direct process coupling.

---

## 14) Shared Scraper State File

State file includes:
- `status`
- `pid`
- `last_change`
- `last_scrape`

Writers:
- scraper UI/worker transitions,
- parse/persist stage updates.

Readers:
- tracker status indicator/tray status,
- scraper window labels.

Writes should be robust (backup/restore handling already exists in state module).

---

## 15) UI Status and Progress Semantics

Scraper window must provide:
- status line (friendly user text),
- pagination progress readout (`Fetching pages... x/y`),
- progress bar activity,
- console log panel,
- last-change and last-scrape summary lines.

Friendly text should suppress noisy internal debug lines and expose user-oriented status messages.

---

## 16) Auth Bootstrap from Settings Window

The **Get auth token** action must:

1. Require auto-capture to be stopped.
2. Persist current settings.
3. Validate URL presence.
4. If credentials incomplete:
   - force non-headless browser
   - log warning in account tab auth log
5. Ensure browser runtime is installed.
6. Run bootstrap worker path.
7. On success:
   - persist auth cache
   - append success line in account log:
     - `Auth bootstrap complete; token cached.`
8. On failure:
   - append warning/error lines in account log.

No mandatory native success popup is required for this flow.

---

## 17) Security and Data Protection Requirements

1. Encrypt stored credentials and auth tokens at rest.
2. Keep auth token cache out of backup exports/import restores.
3. Never parse/apply incomplete paginated captures.
4. Ensure retries/backoff prevent aggressive loops.
5. Avoid leaking internal errors to user-facing status text when a friendly message exists.

---

## 18) Rebuild Acceptance Checklist

Rebuild is complete only if all pass:

1. Start/stop/retry/fault states behave as specified.
2. API pagination enforces `take=50` and incomplete captures are discarded.
3. Auth refresh/bootstrap/manual login flows all work and are logged.
4. Credential/token storage is encrypted and correctly read back.
5. Baseline first run suppresses all-new notification spam.
6. Notifications respect toggles, quiet hours, and mute snapshots.
7. Dump retention limits are enforced for HTML and API dumps.
8. External command file controls (`start/stop/show`) work reliably.
9. Scraper state file markers update and can be consumed by tracker status UI.
10. Get auth token path in settings logs progress and result in account log panel.

