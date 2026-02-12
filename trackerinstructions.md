# FlowerTrack Tracker Rebuild Specification (Language Agnostic)

This document defines the tracker subsystem in full detail.  
It is implementation-language agnostic and should be treated as a behavior contract.

Scope includes:
- tracker data model,
- UI behavior,
- logic trees,
- calculations,
- persistence,
- host/client sync behavior,
- theme and settings integration.

---

## 1) Tracker Purpose

The tracker is the personal dosing and stock system within FlowerTrack.

Primary outcomes:
1. Maintain current flower stock entries.
2. Record dose logs with route-aware cannabinoid mg estimates.
3. Compute daily remaining allowance and days-left stock projections.
4. Provide historical log browsing and period-based stats.
5. Persist all user preferences, UI geometry, and calculation settings.
6. Support network host/client synchronization for shared tracker state.

---

## 2) Core Entities

### 2.1 Flower stock entry

Required fields:
- `name` (string)
- `thc_pct` (float, percent)
- `cbd_pct` (float, percent)
- `grams_remaining` (float, grams)

Derived behavior fields:
- CBD-dominant classification.
- colorization state from threshold rules.

### 2.2 Dose log entry

Required fields:
- timestamp (`ISO` or equivalent + local display format)
- `flower` (stock name reference or mixed entry synthetic name)
- `dose_g` (float grams used)
- `roa` (route key)
- `thc_mg` (float, route-adjusted)
- `cbd_mg` (float, route-adjusted)

Optional fields for mixed dosing:
- `mix_sources`
- `mix_thc_pct`
- `mix_cbd_pct`

### 2.3 Tracker state bundle

Persisted tracker bundle includes:
- flowers list
- logs list
- sort preferences
- column widths
- split ratios
- window geometry
- settings and color overrides

---

## 3) Mode-Aware Tracker Behavior

Tracker runs in one of three app modes:
- standalone
- host
- client

### 3.1 Standalone mode
- Reads and writes local tracker data directly.
- Full feature set enabled.

### 3.2 Host mode
- Same as standalone for local user.
- Also publishes tracker data via network API.
- Applies remote tracker writes atomically.
- Shows active client count near status indicator.

### 3.3 Client mode
- Treat host tracker data as authoritative.
- Local tracker file is not source of truth during active sync.
- Scraper controls disabled.
- Status indicator repurposed to connection health.

---

## 4) High-Level UI Layout

Main tracker window consists of:

1. **Top bar**
   - Settings button
   - Scraper button (hidden/disabled in client mode)
   - Flower Library button
   - Flower Browser button
   - Clock and date
   - Host client-count label (host mode)
   - Status indicator icon

2. **Main split area** (horizontal split, draggable sash)
   - Left panel: flower stock table and stock-entry drawer
   - Right panel:
     - Upper: Log Dose controls and remaining labels
     - Lower: Usage Log table, actions, and stats button

3. **Resizable split persistence**
   - Center sash ratio must persist and restore accurately.
   - Restoration should not snap to fallback after load.

---

## 5) Logic Trees (Authoritative)

### 5.1 Track CBD flower toggle decision tree

Input: `track_cbd_flower` (boolean)

- If `true`:
  - show CBD-specific remaining/day labels,
  - include CBD target and CBD usage metrics,
  - compute separate CBD days-left and average usage.

- If `false`:
  - hide CBD-specific display labels,
  - exclude CBD-dominant flower from THC totals/day-left calculations,
  - present generic wording (`Total flower stock`, `Days of flower left`).

### 5.2 CBD-dominant classification tree

Given flower/log cannabinoids:
- CBD dominant if `cbd_pct >= 5.0`.
- For log entries lacking direct flower object, infer from log fields:
  - prefer mix values if present,
  - otherwise infer from matched stock metadata.

### 5.3 Stock inclusion for THC totals tree

For each stock entry:
- If tracking CBD enabled:
  - include all entries in display totals as defined by UI design.
- If tracking CBD disabled:
  - include only non-CBD-dominant entries for THC-based target/day-left math.

### 5.4 Dose log write tree

On `Log Dose` action:
1. Validate selected flower and dose numeric input.
2. Resolve ROA:
   - if ROA hidden => default route.
   - else use selected route.
3. Convert grams to mg (THC/CBD) using formula and route efficiency.
4. Reduce corresponding stock grams.
5. Persist log + stock atomically in tracker state.
6. Refresh stock table, daily remaining labels, usage log table.

### 5.5 Delete/edit log tree

When deleting or editing a log:
1. Reconstruct previously consumed stock from stored log values.
2. For mixed logs use mix metadata restoration path.
3. Apply edit/delete mutation.
4. Recompute all dependent totals and labels.
5. Persist updated tracker state.

---

## 6) Calculation Specification

### 6.1 Per-dose cannabinoid mg

For a dose `dose_g` and percentages `thc_pct`, `cbd_pct`:

- `raw_thc_mg = dose_g * 1000 * (thc_pct / 100)`
- `raw_cbd_mg = dose_g * 1000 * (cbd_pct / 100)`

Apply route efficiency:
- `eff = roa_efficiency_percent / 100`
- `thc_mg = raw_thc_mg * eff`
- `cbd_mg = raw_cbd_mg * eff`

### 6.2 Remaining today (THC)

- `used_today_thc_g = sum(dose_g for logs on current day that count toward THC totals)`
- `remaining_today_thc_g = target_daily_thc_g - used_today_thc_g`

Display format:
- `Remaining today (THC): <remaining> g / <target> g`

### 6.3 Remaining today (CBD)

If CBD tracking enabled:
- `used_today_cbd_g = sum(dose_g for CBD-counted logs today)`
- `remaining_today_cbd_g = target_daily_cbd_g - used_today_cbd_g`

Display format:
- `Remaining today (CBD): <remaining> g / <target> g`

### 6.4 Days-left (THC target/actual)

Let:
- `counted_stock_thc_g = total grams counted for THC model`
- `target_daily_thc_g = configured target`
- `avg_daily_thc_g = computed average usage`

Then:
- `days_target = counted_stock_thc_g / target_daily_thc_g` if target > 0 else `N/A`
- `days_actual = counted_stock_thc_g / avg_daily_thc_g` if avg > 0 else `N/A`

### 6.5 Days-left (CBD, when enabled)

Let:
- `counted_stock_cbd_g = CBD-eligible stock grams`
- `target_daily_cbd_g`
- `avg_daily_cbd_g`

Then:
- `days_target_cbd = counted_stock_cbd_g / target_daily_cbd_g` if target > 0 else `N/A`
- `days_actual_cbd = counted_stock_cbd_g / avg_daily_cbd_g` if avg > 0 else `N/A`

### 6.6 Average daily usage windowing

Input: `avg_usage_days` (integer)

Process:
1. Build per-day sum map over logs.
2. Apply trailing cutoff window if `avg_usage_days > 0`.
3. Compute average over retained usage days.
4. Return `None` if no valid data points.

### 6.7 Interval stats math

Given period logs:
1. sort timestamps ascending.
2. compute adjacent time deltas in seconds.
3. average interval uses only non-zero deltas.
4. longest interval uses max delta.

---

## 7) Usage Log Table Behavior

Columns include (mode/settings dependent):
- time
- flower
- route (ROA)
- dose (g)
- THC (mg)
- CBD (mg)

### 7.1 ROA hide behavior

When hide-ROA setting enabled:
- hide ROA/THC/CBD columns where applicable by display column set.
- preserve user width preferences for full mode.
- restore width prefs when re-enabling.
- if no prefs exist, auto-balance columns once.

### 7.2 Day navigation

Buttons:
- `< Prev` and `Next >`

Behavior:
- shifts `current_date` by +/- one day.
- refreshes table rows and total-used row for selected date.

### 7.3 Total used row

For non-current days, show daily aggregate summary rows:
- THC totals and averages
- CBD totals/averages when tracking enabled

Apply configured under/over colors against daily targets.

---

## 8) Stats Window Contract

Period tabs/buttons:
- Day
- Week
- Month
- Year
- Export CSV
- Copy stats

Required row order:
1. Average interval
2. Longest interval
3. Average dose
4. Largest dose
5. Smallest dose
6. Average daily THC usage
7. Total THC usage
8. Average daily CBD usage (if enabled)
9. Total CBD usage (if enabled)

Rules:
- no first-dose/last-dose rows.
- no shortest-interval row.
- average interval excludes zero-value intervals.

Window behavior:
- fixed width with compact dead space.
- vertical size adapts to displayed rows without excess padding.
- close and copy/export buttons anchored consistently.

---

## 9) Flower Stock Panel Behavior

### 9.1 Table behavior

Columns:
- Name
- THC (%)
- CBD (%)
- Remaining (g)

Supports:
- sortable columns with remembered sort state.
- persisted per-column widths.
- row colorization based on threshold settings.

### 9.2 Add/Edit stock drawer

Drawer includes:
- name
- THC %
- CBD %
- grams
- add/update action
- delete selected
- mix stock button

Behavior requirements:
- toggle via subtle arrow control.
- opening/closing drawer must not distort panel widths.
- initial state restored correctly at startup.

### 9.3 Selection behavior

- selecting stock row populates entry fields.
- delete flow must handle stale selection IDs safely (avoid “item not found” errors).

---

## 10) Mix Calculators Integration

Two windows:
- mixed dose calculator
- stock mix calculator

Tracker integration requirements:
- launch requests must focus existing instance if already open.
- no duplicate windows.
- geometry (including width) persisted separately for each tool.
- theme and titlebar rules applied consistently.

---

## 11) Status Indicator Behavior

### 11.1 Standalone and host

Indicator reflects scraper state:
- green: running
- orange: errored/warn
- red: stopped

Supports:
- double-click: start/stop scraper
- right-click: mute/unmute scraper notifications
- hover tooltip with delayed display

Host-only addition:
- show active client count label adjacent to indicator.
- indicator semantics remain scraper-focused (not replaced by host count).

### 11.2 Client mode

Indicator repurposed to network connection health:
- green: connected
- orange: interrupted
- red: disconnected

Tooltip reflects connection status + missed poll count.

---

## 12) Settings Surface (Tracker)

Tab order:
1. Tracker settings
2. Window settings
3. Colour settings
4. Theme
5. Data settings

### 12.1 Tracker settings tab

Sections:
- Tracking options
  - Track CBD flower
  - Hide ROA options in log
- Usage targets
  - Daily target THC
  - Daily target CBD
  - Average usage window
- Route efficiency
  - Vaped
  - Eaten
  - Smoked

### 12.2 Window settings tab

- Dark mode
- Show scraper controls
- Show scraper status icon
- Hide mixed dose option
- Hide mix stock option
- Minimize-to-tray toggles
- Status indicator color pickers (running/stopped/errored)

### 12.3 Colour settings tab

Threshold rows (single-line high/low + picker alignment):
- THC total stock
- CBD total stock
- THC individual stock
- CBD individual stock

Usage color rows:
- Remaining today THC/CBD high/low
- Days left THC/CBD high/low
- Total used today THC/CBD under/over

Toggles:
- enable stock coloring
- enable usage coloring

### 12.4 Theme tab

Expose dark/light palette keys:
- background
- foreground
- control background
- border
- accent
- highlight
- highlight text
- list background
- muted

Functions:
- per-key color pickers
- reset palette to defaults
- immediate live apply

### 12.5 Data settings tab

- backup export
- backup import (destructive confirm gate)
- open data folder
- networking fields when mode requires

---

## 13) Theme Application Rules

Theme must apply consistently to tracker surfaces:
- panels/borders
- table headers and rows
- entry/combo controls
- selection highlights
- tooltips
- separators
- scrollbars
- tabs

Selection/readability requirements:
- selected text colors use configured highlight/highlight-text.
- avoid bright/unreadable inactive selection states.

---

## 14) Geometry and Persistence

Persist and restore:
- main window geometry
- settings window geometry
- stats/mix window geometries
- stock/log table column widths
- main split ratio
- drawer visibility state
- screen resolution snapshot

Resolution safety:
- if screen resolution drops vs previous startup, reset risky window positions to safe centered placements.

---

## 15) Host/Client Sync for Tracker Data

### 15.1 Host-side write safety

Host API writes tracker data using:
- synchronized lock strategy,
- atomic file replacement semantics.

### 15.2 Client polling model

Client flow:
1. poll tracker metadata (mtime/version) asynchronously.
2. fetch full tracker payload when changed.
3. apply loaded tracker data to UI.
4. refresh stock/log displays.

Failure handling:
- increment missed poll counter on failures.
- transition indicator state by missed count thresholds.
- close app after sustained disconnect timeout.

---

## 16) Failure Handling and Edge Cases

1. Invalid numeric input in settings:
   - validate, clamp/coerce, and show targeted error.

2. Missing selected tree row on delete/edit:
   - fail gracefully; no uncaught UI exceptions.

3. External tracker file modifications:
   - detect mtime changes and reload safely.

4. Network unavailable in client mode:
   - non-blocking retries,
   - no UI freeze,
   - explicit disconnected state.

5. Hidden ROA mode:
   - ensure columns and width state do not collapse into unreadable layouts.

---

## 17) UX Constraints

- Tracker UI must not flicker on startup.
- Child windows should not appear top-left before snapping.
- Tooltips should have hover delay (~300-500ms).
- Status and labels should use concise human-readable text.
- Avoid noisy internal diagnostics in user-facing labels.

---

## 18) Acceptance Checklist

A rebuild is considered tracker-complete only if all pass:

1. Dose mg calculations match formulas and ROA efficiency.
2. CBD-tracking toggle behavior matches inclusion/exclusion rules.
3. Remaining today and days-left values are correct in both THC-only and THC+CBD modes.
4. Stats window rows and interval logic match required rules/order.
5. Splitter, drawer, and column width persistence are stable across restarts.
6. Mix windows are singleton and theme-consistent.
7. Status indicator semantics are correct in standalone/host/client modes.
8. Settings tabs expose all required options and apply immediately.
9. Client sync updates from host are reflected both directions where expected.
10. No uncaught UI errors for stale selections, missing data, or mode-specific disabled actions.

