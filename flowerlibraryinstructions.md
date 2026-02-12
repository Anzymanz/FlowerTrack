# Flower Library Rebuild Specification (Language Agnostic)

This document is a full behavior contract for rebuilding the Flower Library subsystem.
It is language/framework agnostic and focuses on functionality, logic, data contracts, UX behavior, and integration points.

---

## 1) Purpose

The Flower Library is a curated, user-editable catalog of flower quality and metadata.

Primary goals:
1. Let users maintain quality ratings and product metadata independent of live scraper data.
2. Provide quick lookup and sorting across key flower attributes.
3. Persist all edits safely with backup protection.
4. Stay visually and behaviorally consistent with global app theme settings.
5. Integrate with tracker/network flows (host/client sync handled by parent app orchestration).

---

## 2) Core Data Model

Each library row must support the following fields:

- `brand` (text)
- `strain` (text)
- `origin` (text)
- `cultivator` (text)
- `packager` (text)
- `thc` (number, optional)
- `cbd` (number, optional)
- `price` (number, optional, interpreted as price per gram)
- `smell` (rating 1.0-10.0)
- `taste` (rating 1.0-10.0)
- `effects` (rating 1.0-10.0)
- `strength` (rating 1.0-10.0)
- `value` (rating 1.0-10.0)
- `overall` (computed numeric average of rating fields)
- `search` (virtual UI-only action cell/icon)

### 2.1 Overall score

`overall = average(smell, taste, effects, strength, value)`  
Rounded to 2 decimal places for storage/display.

If legacy entries are missing `overall`, compute and backfill on refresh.

---

## 3) Persistence Contract

### 3.1 Files

- Primary data file: `data/library_data.json`
- Safety backup on write: `data/library_data.json.bak`
- App config source for library window settings: unified app config (library section)

### 3.2 Write safety

Save flow should be atomic:
1. write JSON to temp file,
2. optionally backup existing file,
3. replace target file atomically.

If load fails due to invalid JSON or read error:
- start with empty list,
- notify user with non-fatal warning.

### 3.3 Settings persistence

Library settings to persist:
- `dark_mode` (mirrors global tracker setting)
- `column_widths` (per-table-column)
- `window_geometry`
- `screen_resolution` snapshot

---

## 4) UI Structure

Main window layout:

1. minimal top spacing row (no redundant title label)
2. table container with themed border frame
3. button row:
   - Add Flower
   - Edit Flower
   - Delete Flower
   - Export Library

### 4.1 Table columns (ordered)

1. Brand  
2. Strain  
3. Origin  
4. Cultivator  
5. Packager  
6. THC %  
7. CBD %  
8. Price /g  
9. Smell  
10. Taste  
11. Effects  
12. Strength  
13. Value  
14. Overall  
15. Search (icon column)

Search column header is intentionally blank.

---

## 5) Form Windows (Add/Edit)

Add and Edit use one reusable form model with mode-specific submit behavior.

Fields:
- text fields (brand/origin/cultivator/packager/strain)
- numeric entries (THC/CBD/Price)
- rating spinboxes (smell/taste/strength/effects/value)

Buttons:
- Save
- Cancel

### 5.1 Validation rules

For THC/CBD/Price:
- blank allowed -> store empty value
- otherwise must parse numeric
- normalize to max 2 decimals

For ratings:
- required range 1.0 to 10.0
- allow one decimal precision
- invalid input blocks save with explicit validation error

### 5.2 Edit selection behavior

Edit requires selected row.
If no row selected:
- show informational prompt,
- do not open form.

Delete requires selection; no-op if none selected.

---

## 6) Sorting and Table Interactions

### 6.1 Sorting

All non-search columns are sortable via header click.

Rules:
- toggle asc/desc per column
- numeric columns sort numerically
- text columns sort case-insensitive lexical
- missing/invalid numerics sort deterministically to extremes

### 6.2 Search icon behavior

Search icon appears in each row in final column (e.g., magnifier glyph).

Clicking icon:
1. read row `brand` and `strain`
2. compose query: `"<brand> <strain> medbud.wiki"`
3. open system browser to Google search URL with encoded query.

Clicking non-search cells should behave as normal selection.

### 6.3 Column width persistence

When heading separator/resize action completes:
- capture current widths for all columns,
- save to settings if changed.

Widths restored on next launch.

---

## 7) Theme and Visual Contract

Flower Library must follow global tracker theme continuously.

### 7.1 Theme source of truth

Read from tracker/global config:
- current dark/light mode
- dark and light palette overrides

Poll periodically for changes so external theme edits propagate without restart.

### 7.2 Applied color semantics

Apply palette values to:
- window background
- panel backgrounds
- text foreground
- table background/rows/headings
- table border frame
- scrollbars
- checkboxes/buttons/entries/spinboxes
- selection/highlight colors
- combobox popup/listbox colors if used

### 7.3 Title bar behavior

On supported platforms, request dark title bar when dark mode enabled.

Requirements:
- apply on main window and all child forms,
- re-apply after map/focus/visibility transitions if needed,
- avoid window flash where possible by preparing child windows before show.

---

## 8) Window Management and UX

### 8.1 Child form presentation

Add/Edit form windows should:
- be transient to main library window,
- grab input (modal behavior),
- use same theme and titlebar behavior,
- open near pointer or sensible anchored position,
- avoid top-left flash.

### 8.2 Geometry persistence

Main library window geometry must persist and restore.

### 8.3 Resolution safety

If current screen resolution is lower than saved resolution:
- clear persisted geometry,
- reopen in safe/centered placement,
- update stored resolution snapshot.

---

## 9) Export Behavior

Export button writes current library entries to user-selected JSON file.

Rules:
- prompt for destination and extension,
- write formatted JSON (`indent` friendly),
- on success show confirmation,
- on failure show explicit error.

Export does not mutate internal library state.

---

## 10) Integration with Parent App

### 10.1 Standalone/local

Library reads/writes local library JSON directly.

### 10.2 Host/client networking integration

Networking transport is orchestrated by parent tracker process.
Library responsibilities remain local CRUD in its process.

Parent integration requirements:
- before launching in client mode, parent should pull latest library data from host.
- after library closes in client mode, parent should push updated library data to host.

Library itself should remain transport-agnostic.

---

## 11) Error Handling Expectations

Non-fatal recoverable errors should be surfaced to users with clear messages:
- load parse failure -> warning + empty dataset
- validation failure -> error + keep form open
- export write failure -> error

Internal theme/titlebar failures should fail silently (no crash) and continue with best-effort visuals.

No uncaught exceptions should break CRUD operations.

---

## 12) Acceptance Checklist

Rebuild is complete only if all pass:

1. Add/Edit/Delete CRUD works with validation parity.
2. Overall score auto-computes and backfills legacy entries.
3. Table sorting works for text and numeric fields with direction toggle.
4. Search icon opens correctly composed query URL.
5. Column width and window geometry persist across restarts.
6. Theme changes from tracker propagate live to library.
7. Child forms inherit theme and avoid visible spawn artifacts.
8. Resolution safety resets invalid geometry when screen shrinks.
9. Export JSON succeeds with correct data shape.
10. File writes are atomic and backup behavior is preserved.

