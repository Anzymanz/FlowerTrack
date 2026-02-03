# FlowerTrack

FlowerTrack is a Windows desktop app for tracking medical cannabis usage and stock, with an integrated scraper for Medicann products. It combines a dosage tracker, flower library, and automated price/stock change detection with optional Home Assistant notifications and local HTML snapshots.

## Download (Windows)
[Download](https://github.com/Anzymanz/FlowerTrack/releases/latest) the latest `FlowerTrack.exe` from Releases.

## Features
- Track flower stock, THC/CBD potency, remaining grams, and daily targets.
- Log doses by route of administration with per-day totals.
- Flower Library and Mix Calculator tools.
- Medicann scraper with API-based pagination and change detection (new/removed items, price/stock changes, restocks).
- Home Assistant webhook notifications and optional Windows desktop notifications.
- Local HTML browser with filters, badges, favorites, basket, and image previews.

## Screenshots
### Tracker dashboard
Shows usage, stock, and daily targets in a single view.

<img src="docs/TrackerSS.png?v=20260124b" width="960" />

### Tracker settings
Configure thresholds, routes, and display options.

<img src="docs/TrackerSettingSS.png?v=20260124b" width="500" />

### Usage stats
Shows usage history and trends over time.

<img src="docs/StatsSS.png?v=20260124b" width="360" />

### Flower library
Stores strains, notes, and metadata.

<img src="docs/LibrarySS.png?v=20260124b" width="960" />

### Scraper window
Shows auto-scraper controls, progress, and log output.

<img src="docs/ScraperSS.png?v=20260124b" width="750" />

### Flower Browser
Local webpage with filters, badges, and change highlights.

<img src="docs/WebpageSS.png?v=20260124b" width="960" />

### Flower Browser favorites
Favorites list for quick access.

<img src="docs/WebpageFavoriteSS.png?v=20260124b" width="960" />

### Flower Browser basket
Basket view for comparing items.

<img src="docs/WebpageBasketSS.png?v=20260124b" width="960" />

### Mix calculator
Calculator for blend ratios.

<img src="docs/MixcalcSS.png?v=20260124b" width="500" />

## The Flower Browser (local webpage)
The scraper generates a local HTML page that you can open from the app. It’s designed for fast scanning and filtering of the live product list.

Key features:
- Search, filter, and sort by brand, strain, type, stock, THC, and CBD.
- Visual badges for new/removed items, price movement, out‑of‑stock, and restock highlights.
- Per‑gram pricing and THC/CBD normalization.
- Flags for origin country and irradiation type (where available).
- Brand images with click‑to‑enlarge previews.
- Favorites and basket lists stored locally in the page.

## Scraper behavior
- Logs in (if configured), then navigates to the products page.
- Captures API responses and paginates through the full product list.
- Retries on empty/partial captures using the retry settings.
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
- Uses win10toast for toasts.

## Configuration and data
All user data and configs are stored under:
```
%APPDATA%\FlowerTrack
```
Key files:
- `flowertrack_config.json` (unified tracker + scraper settings)
- Tracker data and library JSON files
- `Exports\` (HTML snapshots)

Credentials and tokens are stored encrypted (DPAPI on Windows).

## Requirements
- Windows 10/11
- Python 3.12 (dev only)
- Playwright browsers (used for authenticated scraping; auto-installed on first run or via `playwright install`)

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
pyinstaller --noconfirm --clean --onefile --windowed --icon assets/icon.ico --add-data "assets;assets" --add-data "flowerlibrary.py;." --add-data "mixcalc.py;." --name FlowerTrack flowertracker.py
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
- `parser.py` HTML parser
- `exports.py` HTML export generation
- `config.py` config persistence and migrations
- `tests/` unit tests
