from __future__ import annotations

import importlib.machinery
import importlib.util
import socket
import os
import sys
import threading
from typing import Callable
import tkinter as tk
from tkinter import messagebox

from ui_tracker import CannabisTracker
from resources import resource_path as _resource_path
from app_core import APP_DIR, CONFIG_FILE, LAST_PARSE_FILE, SCRAPER_STATE_FILE
from config import load_unified_config
from scraper_state import read_scraper_state
from storage import load_last_parse
from network_mode import (
    MODE_CLIENT,
    MODE_HOST,
    MODE_STANDALONE,
    consume_mode_flags,
    get_mode,
)
import json
from pathlib import Path

SINGLE_INSTANCE_HOST = "127.0.0.1"
_SINGLE_INSTANCE_PORTS = {
    MODE_STANDALONE: 47651,
    MODE_HOST: 47652,
    MODE_CLIENT: 47653,
}
CONSOLE_FLAGS = {"-console", "--console"}


def _single_instance_settings(mode: str | None = None) -> tuple[int, bytes]:
    value = (mode or get_mode()).strip().lower()
    port = _SINGLE_INSTANCE_PORTS.get(value, _SINGLE_INSTANCE_PORTS[MODE_STANDALONE])
    token = f"FLOWERTRACK_SHOW_MAIN:{value}".encode("utf-8")
    return port, token


def _send_focus_signal(mode: str | None = None) -> bool:
    port, token = _single_instance_settings(mode)
    try:
        with socket.create_connection((SINGLE_INSTANCE_HOST, port), timeout=0.35) as conn:
            conn.sendall(token)
        return True
    except Exception:
        return False


def _start_focus_listener(on_focus: Callable[[], None], mode: str | None = None) -> socket.socket | None:
    port, token = _single_instance_settings(mode)
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((SINGLE_INSTANCE_HOST, port))
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
                if payload and payload.startswith(token):
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


def _close_pyinstaller_splash() -> None:
    """Close PyInstaller boot splash if present (no-op outside frozen bootloader)."""
    if "_PYI_SPLASH_IPC" not in os.environ:
        return
    if importlib.util.find_spec("pyi_splash") is None:
        return
    try:
        import pyi_splash  # type: ignore

        pyi_splash.update_text("UI Loaded ...")
        pyi_splash.close()
    except Exception:
        # Keep startup resilient even if splash IPC is unavailable.
        pass


def _enable_optional_console() -> None:
    """Enable a Windows console when launched with -console/--console."""
    requested = any(flag in sys.argv for flag in CONSOLE_FLAGS)
    if not requested:
        os.environ.pop("FLOWERTRACK_CONSOLE", None)
        return
    # Strip custom flags so downstream argv checks remain unchanged.
    sys.argv[:] = [arg for arg in sys.argv if arg not in CONSOLE_FLAGS]
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # If a console already exists (for example launched from terminal), reuse it.
        if kernel32.GetConsoleWindow():
            attached = True
        else:
            # Prefer attaching to parent console (single window for parent+child processes).
            attached = bool(kernel32.AttachConsole(-1))
            if not attached:
                attached = bool(kernel32.AllocConsole())
            if not attached:
                return
    except Exception:
        return

    try:
        sys.stdout = open("CONOUT$", "w", buffering=1, encoding="utf-8", errors="replace")
        sys.stderr = open("CONOUT$", "w", buffering=1, encoding="utf-8", errors="replace")
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        os.environ["FLOWERTRACK_CONSOLE"] = "1"
        print("FlowerTrack console enabled.")
    except Exception:
        pass


def main() -> None:
    network_mode = consume_mode_flags()
    _enable_optional_console()
    # Close boot splash as early as possible so long startup work (e.g. network init)
    # does not leave the splash hanging in host/client modes.
    _close_pyinstaller_splash()
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
    if _send_focus_signal(network_mode):
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

    focus_listener = _start_focus_listener(_on_focus_signal, network_mode)

    root = tk.Tk()
    # Prevent the default empty Tk window from flashing before CannabisTracker
    # finishes constructing/styling the main UI.
    try:
        root.withdraw()
    except Exception:
        pass
    app = CannabisTracker(root)
    _close_pyinstaller_splash()
    try:
        root.update_idletasks()
        root.deiconify()
        root.lift()
        # Force a post-map theme pass so the first painted frame is fully themed,
        # not the default white Tk background.
        try:
            app.apply_theme(app.dark_var.get())
        except Exception:
            pass
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
