# Build / Packaging

## Prereqs
- Python 3.12
- Install deps: `pip install -r requirements.txt`
- Download Playwright browser (once, for the build machine): `python -m playwright install chromium`

## Single-file exe (PyInstaller)
Run from repo root:
```
pyinstaller --noconfirm --clean ^
  --onefile --windowed ^
  --icon assets/icon.ico ^
  --name MedicannScraper ^
  medicannscraper.pyw
```

## Runtime assets included by the spec
- `assets/icon.ico` and `assets/icon.png`
- `parser_database.json` (copied to AppData on first run if missing)
- Local export server serves `AppData/Roaming/MedicannScraper/Exports`

## Browser at runtime
- The packaged app still needs a Playwright browser. On first run it will try to install Chromium to `AppData/Roaming/MedicannScraper/pw-browsers` if not present. If that fails, run manually: `python -m playwright install chromium` (or run the built exe once with network access).
