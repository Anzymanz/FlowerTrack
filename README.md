# FlowerTrack

FlowerTrack is a Windows desktop app for tracking medical cannabis usage and stock, with an integrated Medicann scraper and local Flower Browser. It combines a dosage tracker, flower library, API-first catalog capture, and automated price/stock change detection with optional Home Assistant and Windows notifications.

## Download (Windows)
[Download](https://github.com/Anzymanz/FlowerTrack/releases/latest) the latest `FlowerTrack.exe` from Releases.

## Features
- Track flower stock, THC/CBD potency, remaining grams, and daily targets.
- Log doses by route of administration with per-day totals.
- Flower Library and Mix Calculator tools.
- Medicann scraper with API pagination and change detection (new/removed items, price/stock changes, restocks, out-of-stock).
- API auth bootstrap flow (including manual login bootstrap on first run when credentials are missing).
- Home Assistant webhook notifications and optional Windows desktop notifications.
- Local Flower Browser with fixed URL (`/flowerbrowser`), filters, badges, favorites, basket, and image previews.
- Change history viewer in both scraper UI and Flower Browser.
- Theme customization with colour pickers (including tracker thresholds and dark/light palette overrides).

## Screenshots
### Tracker dashboard
Shows usage, stock, and daily targets in a single view.

<img src="docs/TrackerSS.png?v=20260210b" width="960" />

### Usage stats
Shows usage history and trends over time.

<img src="docs/StatsSS.png?v=20260210b" width="360" />

### Flower library
Stores strains, notes, and metadata.

<img src="docs/LibrarySS.png?v=20260210b" width="960" />

### Scraper window
Shows auto-scraper controls, progress, and log output.

<img src="docs/ScraperSS_20260209.png?v=20260210b" width="750" />

### Flower Browser
Local webpage with filters, badges, and change highlights.

<img src="docs/WebpageSS.png?v=20260210b" width="960" />

### Flower Browser favorites
Favorites list for quick access.

<img src="docs/WebpageFavoriteSS.png?v=20260210b" width="960" />

### Flower Browser basket
Basket view for comparing items.

<img src="docs/WebpageBasketSS.png?v=20260210b" width="960" />

### Mix calculator
Calculator for blend ratios.

<img src="docs/MixcalcSS.png?v=20260210b" width="500" />

## The Flower Browser (local webpage)
The scraper generates a local HTML page that you can open from the app. It is served from a fixed local path on the local export server:

`http://127.0.0.1:<port>/flowerbrowser` (default port: `8765`)

It is designed for fast scanning and filtering of the live product list.

Key features:
- Search, filter, and sort by brand, strain, type, stock, THC, and CBD.
- Dedicated irradiation filters (`β` and `γ`) for quick beta/gamma product filtering.
- Visual badges for new/removed items, price movement, out‑of‑stock, and restock highlights.
- Per‑gram pricing and THC/CBD normalization.
- Flags for origin country and irradiation type (where available).
- Brand images with click‑to‑enlarge previews.
- Favorites and basket lists stored locally in the page.
- Live "new page available" banner when a newer export is detected.
- Embedded change history modal with readable detail formatting.

## Scraper behavior
- Uses API-first capture and paginates through the full product list.
- Validates pagination completeness and skips parse/apply on interrupted/partial capture.
- Uses cached auth tokens and refreshes via Playwright bootstrap when required.
- Supports manual visible-browser bootstrap when credentials are incomplete on first run.
- Sends notifications only when changes are detected (per notification toggles).

## Home Assistant setup
1. In Home Assistant, create a webhook automation (Settings → Automations → Create → Webhook).
2. Set the webhook ID (e.g., `flowertrack`) and save the automation.
3. Copy the webhook URL from the automation (it looks like `https://YOUR_HA/api/webhook/flowertrack`).
4. In FlowerTrack → Scraper settings, paste the webhook URL into **Home Assistant webhook URL**.
5. Optional: set a long‑lived access token in **Home Assistant token** if your HA instance requires it.
6. Save settings and use **Send test notification** to verify.

- Payload includes new/removed items, price changes, and stock changes.
- Quiet hours and summary/full detail are configurable.


### Example Home Assistant automation
```yaml
- id: flowertrack_webhook
  alias: FlowerTrack Webhook
  mode: parallel
  trigger:
    - platform: webhook
      webhook_id: flowertrack

  variables:
    new_msg: >
      {% if trigger.json.new_item_summaries %}
        New: {{ trigger.json.new_item_summaries | join(', ') }}
      {% elif trigger.json.new_items %}
        New: {{ trigger.json.new_items | join(', ') }}
      {% else %}{{ '' }}{% endif %}
    removed_msg: >
      {% if trigger.json.removed_item_summaries %}
        Removed: {{ trigger.json.removed_item_summaries | join(', ') }}
      {% else %}{{ '' }}{% endif %}
    price_msg: >
      {% if trigger.json.price_change_summaries %}
        Price: {{ trigger.json.price_change_summaries | join('; ') }}
      {% else %}{{ '' }}{% endif %}
    stock_msg: >
      {% if trigger.json.stock_change_summaries %}
        Stock: {{ trigger.json.stock_change_summaries | join('; ') }}
      {% else %}{{ '' }}{% endif %}
    restock_msg: >
      {% if trigger.json.restock_change_summaries %}
        Restock: {{ trigger.json.restock_change_summaries | join('; ') }}
      {% else %}{{ '' }}{% endif %}
    parts: >
      {{ [new_msg, removed_msg, price_msg, stock_msg, restock_msg]
         | reject('equalto','')
         | reject('equalto', None)
         | list }}
    combined: >
      {% if parts|length > 0 %}
        {{ parts | join(' | ') }}
      {% else %}
        Payload: {{ trigger.json | tojson }}
      {% endif %}

  action:
    - service: notify.mobile_app_pixel_9_pro_xl
      data:
        title: "FlowerTrack Update"
        message: "{{ combined }}"
```

## Desktop notifications
- Enable "Send Windows desktop notifications" in scraper settings.
- Uses `win10toast-click` when available (falls back to `win10toast`).

## Configuration and data
All user data and configs are stored under:
```
%APPDATA%\FlowerTrack
```
Key files:
- `flowertrack_config.json` (unified tracker + scraper settings)
- `data\tracker_data.json` and `data\library_data.json`
- `Exports\` (latest export HTML + `changes_latest.json`)
- `logs\changes.ndjson` (change history)
- `dumps\` (optional API dumps when enabled)

Credentials and tokens are stored encrypted (DPAPI on Windows).

## Requirements
- Windows 10/11
- Python 3.12 (dev only)
- Playwright browsers (used for authenticated scraping; auto-installed on first run or via `playwright install`)
- certifi (dev/runtime dependency for HTTPS validation on fresh PCs)

## Quick start (development)
```powershell
py .\flowertracker.py
```

## Quick start (Windows exe)
1. [Download](https://github.com/Anzymanz/FlowerTrack/releases/latest) the latest `FlowerTrack.exe` from Releases.
2. Run `FlowerTrack.exe` (first run may take a little longer).

## Build (single exe)
Use the one-liner in `buildline.txt`, or:
```powershell
pyinstaller --onefile --windowed --icon assets/icon.ico --add-data "assets;assets" --add-data "flowerlibrary.py;." --add-data "mixcalc.py;." --add-data "mix_utils.py;." --exclude-module setuptools.msvc --name FlowerTrack flowertracker.py
```

## Tests
```powershell
py -m pytest
```

## Troubleshooting
- If Playwright browsers are missing, run:
  ```powershell
  playwright install
  ```
- If the scraper logs "No products parsed", increase wait time or retries.
- If you see SSL/certificate errors on a fresh PC (CERTIFICATE_VERIFY_FAILED), install/update certifi and restart:
  ```powershell
  py -m pip install -U certifi
  ```
  The app uses certifi for API/HA HTTPS validation; missing roots on Windows can cause fetch failures.
- If scraper settings look blank or defaults are missing, delete `%APPDATA%\FlowerTrack\flowertrack_config.json` and relaunch to re-seed defaults.
- Use the console log in-app for detailed scrape output.

## Repository layout
- `flowertracker.py` entry point
- `ui_*.py` UI modules
- `capture.py` scraper worker
- `parser.py` API payload parser and dedupe logic
- `exports.py` + `export_template.py` Flower Browser HTML generation
- `export_server.py` local HTTP server for `/flowerbrowser` and live export events
- `config.py` config persistence and migrations
- `tests/` unit tests
