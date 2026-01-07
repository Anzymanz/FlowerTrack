# FlowerTrack

FlowerTrack is a Windows desktop app for tracking medical cannabis usage and stock, with an integrated scraper that monitors a Medicann page for changes. It combines a dosage tracker, flower library, and automated price/stock change detection with optional Home Assistant notifications and local HTML snapshots.

## Features
- Track flower stock, THC/CBD potency, and remaining grams.
- Log doses by route of administration with per-day stats.
- Flower Library and Mix Calculator tools.
- Scraper for Medicann page data with change detection (new/removed items, price/stock changes).
- Home Assistant webhook notifications and optional Windows desktop notifications.
- Exported HTML snapshots served locally for quick browsing.

## Requirements
- Windows 10/11
- Python 3.12 recommended
- Playwright browsers (installed on first run or via `playwright install`)

## Run (development)
```powershell
py .\flowertracker.py
```

## Build (single exe)
Use the one-liner in `buildline.txt`, or:
```powershell
pyinstaller --noconfirm --clean --onefile --windowed --icon assets/icon.ico --add-data "assets;assets" --add-data "flowerlibrary.py;." --add-data "mixcalc.py;." --name FlowerTrack flowertracker.py
```

## Configuration and data
All user data and configs are stored under:
```
%APPDATA%\FlowerTrack
```
Key files:
- `flowertrack_config.json` (unified tracker + scraper settings)
- Tracker data and library JSON files
- Scraper exports under `Exports\`

## Notes
- The scraper uses Playwright. If you hit browser errors, run: `playwright install`.
- Home Assistant webhook URL and token are stored encrypted.
- The scraper status icon in the tracker window can be toggled in settings.

## Repository layout
- `flowertracker.py` entry point
- `ui_*.py` UI modules
- `capture.py` scraper worker
- `parser.py` HTML parser
- `exports.py` HTML export generation
