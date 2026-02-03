# Contributing to FlowerTrack

Thanks for helping out.

## Setup
- Windows 10/11
- Python 3.12 recommended

Install deps (for dev/build/tests):
```powershell
pip install pyinstaller playwright pillow certifi
```

If Playwright browsers are missing:
```powershell
playwright install
```

## Run (dev)
```powershell
py .\flowertracker.py
```

## Tests
```powershell
py -m unittest discover -s tests -p "test_*.py"
```

## Build (manual release)
Use the one-liner in `buildline.txt`:
```powershell
pyinstaller --noconfirm --clean --onefile --windowed --icon assets/icon.ico --add-data "assets;assets" --add-data "flowerlibrary.py;." --add-data "mixcalc.py;." --name FlowerTrack flowertracker.py
```

## Repo hygiene
- Do not commit `build/`, `dist/`, or `__pycache__/`.
- Keep settings/data under `%APPDATA%\FlowerTrack`.
