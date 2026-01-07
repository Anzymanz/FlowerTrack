# Release process (manual)

Releases are published manually.

## Steps
1) Build the exe locally:
```powershell
pyinstaller --noconfirm --clean --onefile --windowed --icon assets/icon.ico --add-data "assets;assets" --add-data "flowerlibrary.py;." --add-data "mixcalc.py;." --name FlowerTrack flowertracker.pyw
```

2) Smoke test `dist/FlowerTrack.exe`.

3) Create a GitHub Release (tagged) and upload the exe.

## Notes
- Large binaries are not committed to git.
- If Playwright browsers are missing on a new machine, run `playwright install`.
