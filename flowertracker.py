from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import tkinter as tk
from tkinter import messagebox

from ui_tracker import CannabisTracker, _resource_path


def main() -> None:
    if "--run-mixcalc" in sys.argv:
        mix_path = _resource_path("mixcalc.py")
        if not os.path.exists(mix_path):
            messagebox.showerror("Not found", "mixcalc.py not found in the app folder.")
            return
        try:
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
