from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import tkinter as tk
from tkinter import messagebox

from ui_tracker import CannabisTracker
from resources import resource_path as _resource_path
from app_core import APP_DIR, CONFIG_FILE, LAST_PARSE_FILE, SCRAPER_STATE_FILE
from config import load_unified_config
from scraper_state import read_scraper_state
from storage import load_last_parse
import json
from pathlib import Path


def main() -> None:
    if "--diagnostics" in sys.argv:
        try:
            cfg = load_unified_config(Path(CONFIG_FILE), decrypt_scraper_keys=[], write_back=False)
        except Exception as exc:
            cfg = {"error": f"Failed to load config: {exc}"}
        try:
            last_parse = load_last_parse(LAST_PARSE_FILE)
        except Exception as exc:
            last_parse = f"Failed to load last parse: {exc}"
        try:
            scraper_state = read_scraper_state(SCRAPER_STATE_FILE)
        except Exception as exc:
            scraper_state = {"error": f"Failed to read scraper state: {exc}"}
        summary = {
            "app_dir": APP_DIR,
            "config_file": str(CONFIG_FILE),
            "config_loaded": isinstance(cfg, dict),
            "scraper_state_file": str(SCRAPER_STATE_FILE),
            "scraper_state": scraper_state,
            "last_parse_file": str(LAST_PARSE_FILE),
            "last_parse_count": len(last_parse) if isinstance(last_parse, list) else None,
            "last_parse_error": None if isinstance(last_parse, list) else last_parse,
            "config_version": cfg.get("version") if isinstance(cfg, dict) else None,
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return
    if "--run-mixcalc" in sys.argv:
        mix_path = _resource_path("mixcalc.py")
        if not os.path.exists(mix_path):
            messagebox.showerror("Not found", "mixcalc.py not found in the app folder.")
            return
        try:
            mix_dir = os.path.dirname(mix_path)
            if mix_dir and mix_dir not in sys.path:
                sys.path.insert(0, mix_dir)
            loader = importlib.machinery.SourceFileLoader("mixcalc_embedded", mix_path)
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
        except Exception as exc:
            messagebox.showerror("Cannot launch", f"Failed to start mix calculator:\n{exc}")
        return
    if "--scraper" in sys.argv or "--parser" in sys.argv:
        from ui_scraper import App
        app = App()
        app.mainloop()
        return
    if "--run-library" in sys.argv:
        library_path = _resource_path("flowerlibrary.py")
        if not os.path.exists(library_path):
            messagebox.showerror("Not found", "flowerlibrary.py not found in the app folder.")
            return
        try:
            loader = importlib.machinery.SourceFileLoader("flowerlibrary_embedded", library_path)
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
            if hasattr(module, "main"):
                module.main()
            elif hasattr(module, "FlowerLibraryApp"):
                root = tk.Tk()
                module.FlowerLibraryApp(root)
                root.mainloop()
            else:
                messagebox.showerror("Cannot launch", "Library entry point not found.")
        except Exception as exc:
            messagebox.showerror("Cannot launch", f"Failed to start flower library:\n{exc}")
        return

    root = tk.Tk()
    app = CannabisTracker(root)
    app.run()


if __name__ == "__main__":
    main()
