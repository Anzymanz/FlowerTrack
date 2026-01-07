from __future__ import annotations

from typing import Tuple

from app_core import SCRAPER_STATE_FILE
from scraper_state import resolve_scraper_status as resolve_scraper_status_core
from tray import make_tray_image


def resolve_scraper_status(child_procs) -> Tuple[bool, bool]:
    return resolve_scraper_status_core(child_procs, SCRAPER_STATE_FILE)


def build_tray_image(child_procs):
    try:
        running, warn = resolve_scraper_status_core(child_procs, SCRAPER_STATE_FILE)
        return make_tray_image(running=running, warn=warn)
    except Exception:
        return None
