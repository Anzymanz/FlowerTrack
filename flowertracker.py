from __future__ import annotations

import importlib.machinery
import importlib.util
import socket
import os
import sys
import threading
import time
from typing import Callable
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

SINGLE_INSTANCE_HOST = "127.0.0.1"
SINGLE_INSTANCE_PORT = 47651
SINGLE_INSTANCE_TOKEN = b"FLOWERTRACK_SHOW_MAIN"


def _send_focus_signal() -> bool:
    try:
        with socket.create_connection((SINGLE_INSTANCE_HOST, SINGLE_INSTANCE_PORT), timeout=0.35) as conn:
            conn.sendall(SINGLE_INSTANCE_TOKEN)
        return True
    except Exception:
        return False


def _start_focus_listener(on_focus: Callable[[], None]) -> socket.socket | None:
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((SINGLE_INSTANCE_HOST, SINGLE_INSTANCE_PORT))
        server.listen(5)
        server.settimeout(0.5)
    except Exception:
        try:
            server.close()
        except Exception:
            pass
        return None

    def _run() -> None:
        while True:
            try:
                conn, _addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                payload = conn.recv(128)
                if payload and payload.startswith(SINGLE_INSTANCE_TOKEN):
                    try:
                        on_focus()
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    threading.Thread(target=_run, daemon=True, name="single-instance-focus-listener").start()
    return server


def _focus_main_window(app: CannabisTracker) -> None:
    try:
        app._restore_from_tray()
    except Exception:
        pass


def _show_startup_splash(root: tk.Tk) -> tk.Toplevel | None:
    banner_path = _resource_path("assets/Banner.png")
    if not os.path.exists(banner_path):
        banner_path = _resource_path("assets/banner.png")
    if not os.path.exists(banner_path):
        return None
    try:
        splash = tk.Toplevel(root)
        splash.withdraw()
        splash.overrideredirect(True)
        splash.attributes("-topmost", True)
        img = tk.PhotoImage(file=banner_path)
        splash._banner_img = img  # keep reference alive
        lbl = tk.Label(splash, image=img, bd=0, highlightthickness=0)
        lbl.pack()
        splash.update_idletasks()
        width = splash.winfo_width()
        height = splash.winfo_height()
        screen_w = splash.winfo_screenwidth()
        screen_h = splash.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        splash.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        splash.deiconify()
        splash.update_idletasks()
        return splash
    except Exception:
        return None


def _close_startup_splash(splash: tk.Toplevel | None) -> None:
    if splash is None:
        return
    try:
        if tk.Toplevel.winfo_exists(splash):
            splash.destroy()
    except Exception:
        pass
    try:
        app.root.deiconify()
    except Exception:
        pass
    try:
        app.root.lift()
    except Exception:
        pass
    try:
        app.root.focus_force()
    except Exception:
        pass


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
        app = App(start_hidden="--scraper-hidden" in sys.argv)
        if "--scraper-autostart" in sys.argv:
            try:
                app.after(350, app.start_auto_capture)
            except Exception:
                pass
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

    # Main tracker mode only: enforce single instance and restore existing window.
    if _send_focus_signal():
        return

    app_ref: dict[str, CannabisTracker] = {}
    pending_focus = {"value": False}

    def _on_focus_signal() -> None:
        app = app_ref.get("app")
        if app is None:
            pending_focus["value"] = True
            return
        try:
            app.root.after(0, lambda: _focus_main_window(app))
        except Exception:
            pass

    focus_listener = _start_focus_listener(_on_focus_signal)

    root = tk.Tk()
    root.withdraw()
    splash = _show_startup_splash(root)
    splash_started_at = time.perf_counter() if splash is not None else None
    try:
        root.update_idletasks()
        root.update()
    except Exception:
        pass
    try:
        app = CannabisTracker(root)
    finally:
        if splash is not None and splash_started_at is not None:
            elapsed = time.perf_counter() - splash_started_at
            remaining = 2.0 - elapsed
            if remaining > 0:
                try:
                    # Keep splash visible long enough to avoid pop-in flicker on fast starts.
                    time.sleep(remaining)
                except Exception:
                    pass
        _close_startup_splash(splash)
    try:
        root.deiconify()
        root.lift()
        root.focus_force()
    except Exception:
        pass
    app_ref["app"] = app
    if pending_focus["value"]:
        _on_focus_signal()
    try:
        app.run()
    finally:
        try:
            if focus_listener is not None:
                focus_listener.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
