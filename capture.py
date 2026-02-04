from __future__ import annotations

import base64
import json
import os
import sys
import urllib.parse
import urllib.request
import threading
from threading import Event
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Literal, Optional, TypedDict

from net_utils import make_ssl_context
from config import encrypt_secret, decrypt_secret

_Playwright = None

Status = Literal["idle", "running", "retrying", "faulted", "stopped"]

class CaptureStateMachine:
    _transitions = {
        "idle": {"running", "stopped"},
        "running": {"retrying", "faulted", "stopped"},
        "retrying": {"running", "faulted", "stopped"},
        "faulted": {"stopped"},
        "stopped": {"idle", "running"},
    }

    def __init__(self) -> None:
        self.status: Status = "idle"

    def can_transition(self, new_status: Status) -> bool:
        if new_status == self.status:
            return False
        return new_status in self._transitions.get(self.status, set())

    def transition(self, new_status: Status) -> bool:
        if not self.can_transition(new_status):
            return False
        self.status = new_status
        return True


@dataclass(frozen=True)
class RetryPolicy:
    retry_attempts: int
    retry_wait_seconds: float
    backoff_max: float

    @classmethod
    def from_config(cls, cfg: dict) -> "RetryPolicy":
        attempts = max(0, int(cfg.get("retry_attempts", 0)))
        wait = float(cfg.get("retry_wait_seconds", 0) or 0)
        if wait <= 0:
            wait = float(cfg.get("post_nav_wait_seconds", 0) or 0)
        backoff = float(cfg.get("retry_backoff_max", 4) or 4)
        if backoff < 1:
            backoff = 1.0
        return cls(attempts, max(0.0, wait), backoff)

    def attempt_wait(self, attempt: int) -> float:
        if self.retry_wait_seconds <= 0:
            return 0.0
        factor = min(max(1, attempt), self.backoff_max)
        return self.retry_wait_seconds * factor

    def interval_with_backoff(self, base_interval: float, failures: int) -> float:
        if failures <= 0:
            return base_interval
        factor = min(1 + failures, self.backoff_max)
        return base_interval * factor




# Pagination helper for testability
def pagination_is_complete(data_list, total, pagination_failed) -> bool:
    if pagination_failed and total and isinstance(data_list, list) and len(data_list) < total:
        return False
    return True

class CaptureCallbacks(TypedDict, total=False):
    capture_log: Callable[[str], None]
    apply_text: Callable[[str], None]
    on_stop: Callable[[], None]
    on_status: Callable[[Status, Optional[str]], None]
    responsive_wait: Callable[[float, str], bool]
    stop_event: threading.Event
    on_error: Optional[Callable[[str], None]]
    on_done: Optional[Callable[[], None]]
    update_tray: Optional[Callable[[str], None]]


class CaptureWorker:
    """Encapsulated Playwright worker with simple state management."""

    _BACKOFF_LOG_EVERY = 3

    def __init__(
        self,
        cfg: dict,
        callbacks: CaptureCallbacks,
        app_dir: Optional[Path],
        install_fn: Optional[Callable[[], bool]],
    ):
        self.cfg: dict = cfg
        self.callbacks: CaptureCallbacks = callbacks
        self.formulary_headers: dict | None = None
        self.formulary_base_url: str | None = None
        self.formulary_cookie_header: str | None = None
        self.app_dir = app_dir
        self.install_fn = install_fn
        self.thread: Optional[threading.Thread] = None
        self.state = CaptureStateMachine()
        self.status: Status = self.state.status
        self.empty_failures: int = 0
        self.retry_policy = RetryPolicy.from_config(cfg)
        self.retry_attempts = self.retry_policy.retry_attempts
        self.scheduler = IntervalScheduler(self.callbacks["stop_event"], self.callbacks["responsive_wait"])
        self._backoff_logged_for: int = 0

    def _safe_log(self, msg: str) -> None:
        try:
            self.callbacks.get("capture_log", lambda m: None)(msg)
        except Exception:
            try:
                print(msg)
            except Exception:
                pass

    def _auth_cache_path(self) -> Path:
        if self.app_dir:
            return Path(self.app_dir) / "data" / "api_auth.json"
        appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
        return appdata / "FlowerTrack" / "data" / "api_auth.json"

    def _decode_jwt_payload(self, token: str) -> dict:
        try:
            raw = token.strip()
            if raw.lower().startswith("bearer "):
                raw = raw[7:].strip()
            parts = raw.split(".")
            if len(parts) < 2:
                return {}
            payload_b64 = parts[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
            return json.loads(decoded.decode("utf-8"))
        except Exception:
            return {}

    def _extract_auth_from_payloads(self, api_payloads: list[dict]) -> dict | None:
        rpc_host = None
        patient_id = None
        pharmacy_id = None
        token = None
        refresh_token = None
        user_agent = None

        for payload in api_payloads:
            url = payload.get("url") or ""
            if "production-rpc-api" in url:
                try:
                    rpc_host = urllib.parse.urlparse(url).netloc
                except Exception:
                    pass
            if "formulary-products" in url:
                try:
                    parsed = urllib.parse.urlparse(url)
                    q = urllib.parse.parse_qs(parsed.query)
                    patient_id = q.get("patientId", [patient_id])[0]
                    pharmacy_id = q.get("pharmacyId", [pharmacy_id])[0]
                except Exception:
                    pass
            req_headers = payload.get("request_headers") or {}
            if isinstance(req_headers, dict):
                token = token or req_headers.get("authorization") or req_headers.get("Authorization")
                user_agent = user_agent or req_headers.get("user-agent") or req_headers.get("User-Agent")

        for payload in api_payloads:
            url = payload.get("url") or ""
            data = payload.get("data")
            if "auth/initialize" in url and isinstance(data, dict):
                tokens = data.get("tokens") or {}
                access = tokens.get("accessToken")
                refresh = tokens.get("refreshToken")
                if access:
                    token = token or f"Bearer {access}"
                if refresh:
                    refresh_token = refresh

        if token and (patient_id is None or pharmacy_id is None):
            jwt_payload = self._decode_jwt_payload(token)
            if patient_id is None:
                patient_id = jwt_payload.get("roleEntityId")
            ctx = jwt_payload.get("context") if isinstance(jwt_payload, dict) else None
            if pharmacy_id is None and isinstance(ctx, dict):
                pharmacy_id = ctx.get("organizationId")

        if not token or not rpc_host or not patient_id or not pharmacy_id:
            return None

        return {
            "token": token,
            "refresh_token": refresh_token,
            "patient_id": patient_id,
            "pharmacy_id": pharmacy_id,
            "rpc_host": rpc_host,
            "user_agent": user_agent,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    def _persist_auth_cache(self, api_payloads: list[dict]) -> None:
        auth = self._extract_auth_from_payloads(api_payloads)
        if not auth:
            return
        try:
            if auth.get("token"):
                auth["token"] = encrypt_secret(str(auth["token"]))
            if auth.get("refresh_token"):
                auth["refresh_token"] = encrypt_secret(str(auth["refresh_token"]))
        except Exception as exc:
            self._safe_log(f"Auth cache encryption failed: {exc}")
        path = self._auth_cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(auth, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            self._safe_log(f"Auth cache write failed: {exc}")

    def _load_auth_cache(self) -> dict | None:
        path = self._auth_cache_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            try:
                token = data.get("token")
                if token:
                    data["token"] = decrypt_secret(str(token))
                refresh = data.get("refresh_token")
                if refresh:
                    data["refresh_token"] = decrypt_secret(str(refresh))
            except Exception:
                pass
            return data
        except Exception:
            return None

    def _auth_is_expired(self, token: str) -> bool:
        payload = self._decode_jwt_payload(token)
        exp = payload.get("exp")
        try:
            if exp is None:
                return False
            return time.time() > (float(exp) - 60)
        except Exception:
            return False

    def _auth_cache_valid(self) -> bool:
        auth = self._load_auth_cache()
        if not auth:
            return False
        token = auth.get("token")
        if not token or self._auth_is_expired(str(token)):
            return False
        rpc_host = auth.get("rpc_host")
        patient_id = auth.get("patient_id")
        pharmacy_id = auth.get("pharmacy_id")
        if not rpc_host or not patient_id or not pharmacy_id:
            return False
        return True

    def _direct_api_capture(self) -> list[dict] | None:
        auth = self._load_auth_cache()
        if not auth:
            return None
        token = auth.get("token")
        if not token or self._auth_is_expired(str(token)):
            return None
        rpc_host = auth.get("rpc_host")
        patient_id = auth.get("patient_id")
        pharmacy_id = auth.get("pharmacy_id")
        if not rpc_host or not patient_id or not pharmacy_id:
            return None
        headers = {
            "authorization": str(token),
            "accept": "application/json",
        }
        user_agent = auth.get("user_agent")
        if user_agent:
            headers["user-agent"] = str(user_agent)

        include_inactive = bool(self.cfg.get("include_inactive", False))
        requestable_only = bool(self.cfg.get("requestable_only", True))
        in_stock_only = bool(self.cfg.get("in_stock_only", False))
        base_url = (
            f"https://{rpc_host}/formulary-products?"
            f"patientId={patient_id}&pharmacyId={pharmacy_id}"
            f"&productType=CANNABIS_PRODUCT&take=50&skip=0"
            f"&includeInactive={'true' if include_inactive else 'false'}"
            f"&requestableOnly={'true' if requestable_only else 'false'}"
            f"&requireAvailableStock={'true' if in_stock_only else 'false'}"
        )

        def _http_get_json(url: str):
            attempts = 3
            ssl_ctx = make_ssl_context()
            for attempt in range(1, attempts + 1):
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=20, context=ssl_ctx) as resp:
                        status = getattr(resp, "status", None) or resp.getcode()
                        body = resp.read()
                    return json.loads(body.decode("utf-8")), status
                except Exception as exc:
                    self.callbacks["capture_log"](
                        f"API fetch failed (attempt {attempt}/{attempts}): {exc}"
                    )
                    if attempt < attempts:
                        try:
                            self.callbacks["responsive_wait"](1.0 * attempt, label="API retry")
                        except Exception:
                            time.sleep(1.0 * attempt)
            return None

        api_payloads: list[dict] = []
        start_ts = time.time()
        data_list_resp = _http_get_json(base_url)
        if not data_list_resp or not isinstance(data_list_resp[0], list):
            return None
        data_list, base_status = data_list_resp
        api_payloads.append({
            "url": base_url,
            "content_type": "application/json",
            "kind": "list",
            "count": len(data_list),
            "data": data_list,
            "request_headers": headers,
        })
        # count endpoint for pagination
        try:
            parsed = urllib.parse.urlparse(base_url)
            q = urllib.parse.parse_qs(parsed.query)
            q.pop("take", None)
            q.pop("skip", None)
            count_path = parsed.path.replace("formulary-products", "formulary-products/count")
            count_url = urllib.parse.urlunparse(parsed._replace(path=count_path, query=urllib.parse.urlencode(q, doseq=True)))
            count_resp = _http_get_json(count_url)
        except Exception:
            count_resp = None
        total = None
        count_status = None
        if count_resp and isinstance(count_resp[0], dict):
            count_data, count_status = count_resp
            total = count_data.get("count") or count_data.get("total")
        if total is None:
            total = len(data_list)
        try:
            status_txt = f" status={count_status}" if count_status is not None else ""
            self.callbacks["capture_log"](f"API count fetch{status_txt} total={total}")
        except Exception:
            pass
        take = 50
        try:
            self.callbacks["capture_log"](f"API pagination: base={len(data_list)} total={total} take={take}")
        except Exception:
            pass
        if total and len(data_list) < total:
            for skip in range(take, int(total), take):
                if self.callbacks["stop_event"].is_set():
                    break
                try:
                    parsed = urllib.parse.urlparse(base_url)
                    q = urllib.parse.parse_qs(parsed.query)
                    q["skip"] = [str(skip)]
                    q["take"] = [str(take)]
                    next_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(q, doseq=True)))
                    more_resp = _http_get_json(next_url)
                    if more_resp and isinstance(more_resp[0], list):
                        more, more_status = more_resp
                        try:
                            status_txt = f" status={more_status}" if more_status is not None else ""
                            self.callbacks["capture_log"](f"API pagination fetch skip={skip}{status_txt}")
                        except Exception:
                            pass
                        api_payloads.append({
                            "url": next_url,
                            "content_type": "application/json",
                            "kind": "list",
                            "count": len(more),
                            "data": more,
                            "request_headers": headers,
                        })
                    else:
                        try:
                            self.callbacks["capture_log"](f"API pagination fetch skip={skip} status=error")
                        except Exception:
                            pass
                except Exception:
                    break
        try:
            elapsed = time.time() - start_ts
            self.callbacks["capture_log"](f"API capture fetched {len(api_payloads)} payloads in {elapsed:.1f}s")
        except Exception:
            pass
        return api_payloads

    def _ensure_playwright_ready(self) -> bool:
        global _Playwright
        if _Playwright:
            return True
        app_dir = self.app_dir or Path(os.getcwd())
        try:
            req = ensure_browser_available(app_dir, self.callbacks.get("capture_log", lambda m: None), install_cb=self.install_fn)
        except Exception as exc:
            self._safe_log(f"Playwright init failed: {exc}")
            return False
        if not req:
            self._safe_log("Playwright not available for auth bootstrap.")
            return False
        return True

    def _bootstrap_auth_with_playwright(self) -> list[dict] | None:
        if not self._ensure_playwright_ready():
            return None
        if self.callbacks["stop_event"].is_set():
            return None
        sync_playwright, PlaywrightTimeoutError = _Playwright
        api_payloads: list[dict] = []
        captured_auth = {"ready": False}

        def _capture_request(req):
            try:
                url = req.url or ""
                if not url:
                    return
                if not any(tok in url for tok in ("formulary-products", "auth/initialize", "rpc-api")):
                    return
                payload = {"url": url}
                try:
                    req_headers = req.headers
                    if isinstance(req_headers, dict):
                        payload["request_headers"] = dict(req_headers)
                except Exception:
                    pass
                api_payloads.append(payload)
                if "formulary-products" in url:
                    headers = payload.get("request_headers") or {}
                    token = headers.get("authorization") or headers.get("Authorization")
                    if token:
                        captured_auth["ready"] = True
            except Exception:
                pass

        def _capture_response(resp):
            try:
                url = resp.url or ""
                if "auth/initialize" not in url:
                    return
                data = None
                try:
                    data = resp.json()
                except Exception:
                    try:
                        raw = resp.text()
                        data = json.loads(raw)
                    except Exception:
                        data = None
                if data is None:
                    return
                payload = {"url": url, "content_type": (resp.headers.get("content-type") or "").lower()}
                payload["data"] = data
                api_payloads.append(payload)
            except Exception:
                pass

        with sync_playwright() as p:
            browser = None
            try:
                browser = p.chromium.launch(headless=self.cfg.get("headless", True))
            except Exception as exc:
                self._safe_log(f"Auth bootstrap browser launch failed: {exc}")
                return None
            try:
                self.callbacks["capture_log"]("Auth bootstrap: browser launched.")
            except Exception:
                pass
            page = browser.new_page()
            try:
                page.on("request", _capture_request)
                page.on("response", _capture_response)
            except Exception:
                pass
            nav_timeout = self.cfg.get("timeout_ms") or self.cfg.get("timeout") or 45000
            try:
                page.set_default_timeout(nav_timeout)
                page.set_default_navigation_timeout(nav_timeout)
            except Exception:
                pass
            try:
                page.goto(self.cfg["url"], timeout=0, wait_until="domcontentloaded")
            except Exception:
                pass
            # Short wait for form/UI to render.
            time.sleep(3)
            try:
                self.callbacks["capture_log"]("Auth missing; launching browser to refresh token...")
            except Exception:
                pass
            try:
                user_sels = [
                    self.cfg.get("username_selector") or "",
                    'input[data-path="email"]',
                    'input[placeholder="Email"]',
                    'input[type="email"]',
                    'input#email',
                    'input[name="email"]',
                ]
                pass_sels = [
                    self.cfg.get("password_selector") or "",
                    'input[data-path="password"]',
                    'input[placeholder="Password"]',
                    'input[type="password"]',
                    'input#password',
                    'input[name="password"]',
                ]
                btn_sels = [
                    self.cfg.get("login_button_selector") or "",
                    'button[type="submit"]',
                    'button:has-text("Sign in")',
                    'button:has-text("Login")',
                ]
                user_union = ",".join([s for s in user_sels if s])
                pass_union = ",".join([s for s in pass_sels if s])
                btn_union = ",".join([s for s in btn_sels if s])

                org_value = (self.cfg.get("organization") or "").strip()
                if org_value:
                    org_sels = [
                        self.cfg.get("organization_selector") or "",
                        'select[name="organization"]',
                        'select#organization',
                        'input[data-path="organization"]',
                        'input[placeholder="Organization"]',
                        '[data-path="organization"]',
                    ]
                    org_union = ",".join([s for s in org_sels if s])
                    if org_union:
                        try:
                            page.select_option(org_union, label=org_value)
                        except Exception:
                            try:
                                loc = page.wait_for_selector(org_union, timeout=5000)
                                loc.click()
                                try:
                                    page.click(f"text={org_value}")
                                except Exception:
                                    page.keyboard.type(org_value)
                                    page.keyboard.press("Enter")
                            except Exception:
                                pass
                if self.cfg.get("username") and user_union:
                    try:
                        loc = page.wait_for_selector(user_union, timeout=10000)
                        loc.fill(self.cfg["username"])
                    except Exception:
                        pass
                if self.cfg.get("password") and pass_union:
                    try:
                        loc = page.wait_for_selector(pass_union, timeout=10000)
                        loc.fill(self.cfg["password"])
                    except Exception:
                        pass
                clicked = False
                if btn_union:
                    try:
                        page.wait_for_selector(btn_union, timeout=5000)
                        page.click(btn_union)
                        clicked = True
                    except Exception:
                        clicked = False
                if not clicked:
                    try:
                        page.keyboard.press("Enter")
                    except Exception:
                        pass
            except PlaywrightTimeoutError:
                pass
            except Exception:
                pass
            wait_login = self.cfg.get("login_wait_seconds", 0)
            if wait_login:
                try:
                    self.callbacks["responsive_wait"](wait_login, label="Waiting after login")
                except Exception:
                    time.sleep(wait_login)
            try:
                page.goto(self.cfg["url"], timeout=0, wait_until="domcontentloaded")
            except Exception:
                pass
            wait_post = max(self.cfg.get("post_nav_wait_seconds", 0), 0)
            if wait_post:
                try:
                    self.callbacks["responsive_wait"](wait_post, label="Waiting after navigation")
                except Exception:
                    time.sleep(wait_post)
            try:
                self.callbacks["capture_log"]("Auth bootstrap: waiting for API auth headers.")
            except Exception:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            start = time.time()
            while not captured_auth["ready"] and (time.time() - start) < 20:
                if self.callbacks["stop_event"].is_set():
                    break
                try:
                    self.callbacks["responsive_wait"](0.5, label="Waiting for auth bootstrap")
                except Exception:
                    time.sleep(0.5)
            try:
                browser.close()
            except Exception:
                pass
            try:
                if captured_auth["ready"]:
                    self.callbacks["capture_log"]("Auth bootstrap: token captured, closing browser.")
                else:
                    self.callbacks["capture_log"]("Auth bootstrap: token not captured before timeout.")
            except Exception:
                pass
        if not api_payloads:
            return None
        if not self._extract_auth_from_payloads(api_payloads):
            return None
        return api_payloads

    def _set_status(self, status: Status, msg: Optional[str] = None):
        if msg:
            self.callbacks.get("capture_log", lambda m: None)(msg)
        changed = self.state.transition(status)
        if not changed and status != self.status:
            self.callbacks.get("capture_log", lambda m: None)(
                f"Ignored invalid state transition {self.status} -> {status}"
            )
        if changed:
            self.status = self.state.status
            cb = self.callbacks.get("on_status")
            if cb:
                try:
                    cb(self.status, msg)
                except Exception as exc:
                    self._safe_log(f"Status callback failed for {self.status}: {exc}")

    def start(self) -> threading.Thread:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self.thread

    def _run(self):
        try:
            self._set_status("running", "Auto-capture started.")
            if self.cfg.get("api_only", True):
                while not self.callbacks["stop_event"].is_set():
                    self._set_status("running", "API capture running...")
                    api_payloads = self._direct_api_capture()
                    if not api_payloads and not self._auth_cache_valid():
                        try:
                            self.callbacks["capture_log"]("Auth cache missing/expired; attempting bootstrap.")
                        except Exception:
                            pass
                        bootstrap_payloads = self._bootstrap_auth_with_playwright()
                        if bootstrap_payloads:
                            try:
                                self._persist_auth_cache(bootstrap_payloads)
                            except Exception as exc:
                                self._safe_log(f"Auth bootstrap persist failed: {exc}")
                            api_payloads = self._direct_api_capture()
                        else:
                            try:
                                self.callbacks["capture_log"]("Auth bootstrap failed; retrying later.")
                            except Exception:
                                pass
                    if api_payloads:
                        try:
                            # Persist auth cache and optionally dump data
                            self._persist_auth_cache(api_payloads)
                            dump_dir = Path(self.app_dir) / "data" if self.app_dir else None
                            stamp = time.strftime("%Y%m%d_%H%M%S")
                            if dump_dir:
                                dump_dir.mkdir(parents=True, exist_ok=True)
                                if self.cfg.get("dump_api_json"):
                                    try:
                                        api_path = dump_dir / f"api_dump_{stamp}.json"
                                        api_path.write_text(json.dumps(api_payloads, ensure_ascii=False, indent=2), encoding="utf-8")
                                        self.callbacks["capture_log"](f"Saved API dump: {api_path}")
                                    except Exception as exc:
                                        self.callbacks["capture_log"](f"API dump failed: {exc}")
                            self.callbacks["apply_text"]("")
                        except Exception as exc:
                            self._safe_log(f"API capture apply failed: {exc}")
                    else:
                        self._set_status("retrying", "API capture failed; waiting before retry.")
                    interval = self.scheduler.next_interval(self.cfg["interval_seconds"], self.cfg)
                    if self.scheduler.wait(interval, label="Waiting for next capture"):
                        break
                self._set_status("stopped")
                return
            sync_playwright, PlaywrightTimeoutError = _Playwright
            with sync_playwright() as p:
                attempted_install = False
                while not self.callbacks["stop_event"].is_set():
                    browser = None
                    while browser is None:
                        try:
                            browser = p.chromium.launch(headless=self.cfg.get("headless", True))
                        except Exception as exc:
                            if self.install_fn and not attempted_install:
                                attempted_install = True
                                self.callbacks["capture_log"]("Playwright browser missing; attempting download...")
                                if self.install_fn():
                                    continue
                            self._set_status("faulted", f"Browser launch failed: {exc}")
                            return
                    page = browser.new_page()
                    api_payloads = []
                    xhr_urls = []
                    endpoint_summaries = []
                    def _capture_response(resp):
                        try:
                            ctype = (resp.headers.get("content-type") or "").lower()
                            url = resp.url or ""
                            req = resp.request
                            rtype = (req.resource_type or "").lower() if req else ""
                            if rtype in ("xhr", "fetch"):
                                if url and len(xhr_urls) < 50:
                                    xhr_urls.append(url)
                            wants_data = any(tok in url for tok in ("formulary", "rpc-api", "entity-api", "api"))
                            if not wants_data and "json" not in ctype and rtype not in ("xhr", "fetch"):
                                return
                            data = None
                            parse_failed = False
                            try:
                                data = resp.json()
                            except Exception:
                                parse_failed = True
                            if parse_failed:
                                try:
                                    raw = resp.text()
                                    data = json.loads(raw)
                                    parse_failed = False
                                except Exception as exc:
                                    if any(tok in url for tok in ("formulary-products", "formulary-products/count")):
                                        self._safe_log(f"Response JSON parse failed for {url}: {exc}")
                            if parse_failed:
                                return
                        except Exception as exc:
                            self._safe_log(f"Response capture failed: {exc}")
                            return
                        try:
                            if isinstance(data, list) and data and isinstance(data[0], dict):
                                if "formulary-products" in (url or ""):
                                    try:
                                        self.formulary_base_url = url
                                    except Exception:
                                        pass
                                    try:
                                        req_headers = resp.request.headers
                                        if isinstance(req_headers, dict):
                                            self.formulary_headers = {k: v for k, v in req_headers.items() if k.lower() not in ("accept-encoding", "host", "content-length")}
                                    except Exception:
                                        pass
                                    try:
                                        cookies = page.context.cookies()
                                        if cookies:
                                            parts = []
                                            for c in cookies:
                                                name = c.get("name")
                                                if name:
                                                    parts.append(f"{name}={c.get('value')}")
                                            if parts:
                                                self.formulary_cookie_header = "; ".join(parts)
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        try:
                            req_headers = None
                            try:
                                req_headers = resp.request.headers if resp.request else None
                            except Exception:
                                req_headers = None
                            filtered_headers = None
                            if isinstance(req_headers, dict):
                                filtered_headers = {
                                    k: v
                                    for k, v in req_headers.items()
                                    if k.lower() not in ("accept-encoding", "host", "content-length")
                                }
                            payload = {"url": resp.url, "content_type": ctype, "status": getattr(resp, "status", None)}
                            if filtered_headers:
                                payload["request_headers"] = filtered_headers
                            try:
                                resp_headers = resp.headers
                                if isinstance(resp_headers, dict):
                                    payload["response_headers"] = dict(resp_headers)
                            except Exception:
                                pass
                            if self.formulary_cookie_header:
                                payload["cookie_header"] = self.formulary_cookie_header
                            if data is not None:
                                if isinstance(data, dict):
                                    payload["kind"] = "dict"
                                    payload["keys"] = list(data.keys())[:50]
                                elif isinstance(data, list):
                                    payload["kind"] = "list"
                                    payload["count"] = len(data)
                                else:
                                    payload["kind"] = type(data).__name__
                                try:
                                    import json as _json
                                    raw = _json.dumps(data, ensure_ascii=False)
                                    if len(raw) <= 8_000_000:
                                        payload["data"] = data
                                    else:
                                        payload["data_truncated"] = raw[:2000]
                                except Exception:
                                    pass
                            else:
                                try:
                                    body = resp.body()
                                    if body:
                                        payload["body_truncated"] = body[:2000].decode(errors="replace")
                                except Exception:
                                    pass
                            api_payloads.append(payload)
                            try:
                                summary = {"url": resp.url, "status": getattr(resp, "status", None), "content_type": ctype}
                                if data is not None:
                                    if isinstance(data, dict):
                                        summary["kind"] = "dict"
                                        summary["keys"] = list(data.keys())[:50]
                                    elif isinstance(data, list):
                                        summary["kind"] = "list"
                                        summary["count"] = len(data)
                                    else:
                                        summary["kind"] = type(data).__name__
                                endpoint_summaries.append(summary)
                            except Exception:
                                pass
                        except Exception:
                            pass

                    try:
                        page.on("response", _capture_response)
                    except Exception:
                        pass
                    nav_timeout = self.cfg.get("timeout_ms") or self.cfg.get("timeout") or 45000
                    try:
                        page.set_default_timeout(nav_timeout)
                    except Exception:
                        pass
                    try:
                        page.set_default_navigation_timeout(nav_timeout)
                    except Exception:
                        pass

                    def safe_goto(url: str, label: str) -> bool:
                        """Navigate without enforcing a timeout to avoid getting stuck on long-running page scripts."""
                        try:
                            page.goto(url, timeout=0, wait_until="domcontentloaded")
                        except PlaywrightTimeoutError:
                            self.callbacks["capture_log"](f"{label}: navigation timed out; continuing.")
                        except Exception as exc:
                            self.callbacks["capture_log"](f"{label}: navigation error; continuing. ({exc})")
                        return True

                    restart_browser = False
                    first_cycle = True
                    while not self.callbacks["stop_event"].is_set():
                        self._set_status("running", f"Navigating to {self.cfg['url']}")
                        api_payloads.clear()
                        self.formulary_headers = None
                        self.formulary_base_url = None
                        self.formulary_cookie_header = None
                        try:
                            retries_left = self.retry_policy.retry_attempts
                            wait_post = max(self.cfg.get("post_nav_wait_seconds", 0), 0)
                            if first_cycle:
                                if not safe_goto(self.cfg["url"], "First visit"):
                                    self._set_status("retrying", "Navigation failed; retrying shortly.")
                                    self.callbacks["responsive_wait"](10, label="Retry after navigation failure")
                                    continue
                                # Try to log in with explicit waits for selectors
                                self.callbacks["capture_log"]("Attempting login...")
                                try:
                                    user_sels = [
                                        self.cfg.get("username_selector") or "",
                                        'input[data-path="email"]',
                                        'input[placeholder="Email"]',
                                        'input[type="email"]',
                                        'input#email',
                                        'input[name="email"]',
                                    ]
                                    pass_sels = [
                                        self.cfg.get("password_selector") or "",
                                        'input[data-path="password"]',
                                        'input[placeholder="Password"]',
                                        'input[type="password"]',
                                        'input#password',
                                        'input[name="password"]',
                                    ]
                                    btn_sels = [
                                        self.cfg.get("login_button_selector") or "",
                                        'button[type="submit"]',
                                        'button:has-text("Sign in")',
                                        'button:has-text("Login")',
                                    ]
                                    user_union = ",".join([s for s in user_sels if s])
                                    pass_union = ",".join([s for s in pass_sels if s])
                                    btn_union = ",".join([s for s in btn_sels if s])

                                    # Short wait for form to render
                                    time.sleep(3)

                                    org_value = (self.cfg.get("organization") or "").strip()
                                    if org_value:
                                        org_sels = [
                                            self.cfg.get("organization_selector") or "",
                                            'select[name="organization"]',
                                            'select#organization',
                                            'input[data-path="organization"]',
                                            'input[placeholder="Organization"]',
                                            '[data-path="organization"]',
                                        ]
                                        org_union = ",".join([s for s in org_sels if s])
                                        if org_union:
                                            try:
                                                page.select_option(org_union, label=org_value)
                                                self.callbacks["capture_log"]("Selected organization via select option.")
                                            except Exception:
                                                try:
                                                    loc = page.wait_for_selector(org_union, timeout=5000)
                                                    loc.click()
                                                    try:
                                                        page.click(f"text={org_value}")
                                                    except Exception:
                                                        page.keyboard.type(org_value)
                                                        page.keyboard.press("Enter")
                                                    self.callbacks["capture_log"]("Selected organization via dropdown.")
                                                except Exception:
                                                    self.callbacks["capture_log"]("Organization selector not found.")
                                    if self.cfg.get("username") and user_union:
                                        try:
                                            loc = page.wait_for_selector(user_union, timeout=10000)
                                            loc.fill(self.cfg["username"])
                                            self.callbacks["capture_log"](f"Filled username via union selector.")
                                        except Exception:
                                            self.callbacks["capture_log"]("Username selector not found.")
                                    if self.cfg.get("password") and pass_union:
                                        try:
                                            loc = page.wait_for_selector(pass_union, timeout=10000)
                                            loc.fill(self.cfg["password"])
                                            self.callbacks["capture_log"](f"Filled password via union selector.")
                                        except Exception:
                                            self.callbacks["capture_log"]("Password selector not found.")
                                    clicked = False
                                    if btn_union:
                                        try:
                                            page.wait_for_selector(btn_union, timeout=5000)
                                            page.click(btn_union)
                                            clicked = True
                                            self.callbacks["capture_log"](f"Clicked login via union selector.")
                                        except Exception:
                                            clicked = False
                                    if not clicked:
                                        page.keyboard.press("Enter")
                                except PlaywrightTimeoutError:
                                    self.callbacks["capture_log"]("Login selectors not found; will retry.")
                                    self._set_status("retrying", "Login selectors not found.")
                                    continue
                                wait_login = self.cfg.get("login_wait_seconds", 0)
                                if wait_login:
                                    self.callbacks["capture_log"](f"Waiting {wait_login}s after login")
                                    if self.callbacks["responsive_wait"](wait_login, label="Waiting after login"):
                                        break
                                if not safe_goto(self.cfg["url"], "Revisit"):
                                    self._set_status("retrying", "Navigation failed after login; retrying shortly.")
                                    self.callbacks["responsive_wait"](10, label="Retry after navigation failure")
                                    continue
                            else:
                                if not safe_goto(self.cfg["url"], "Refresh"):
                                    self._set_status("retrying", "Navigation failed; retrying shortly.")
                                    self.callbacks["responsive_wait"](10, label="Retry after navigation failure")
                                    continue
                            if wait_post:
                                self.callbacks["capture_log"](f"Waiting {wait_post}s after navigation")
                                if self.callbacks["responsive_wait"](wait_post, label="Waiting after navigation"):
                                    break
                            try:
                                page.wait_for_load_state("networkidle", timeout=20000)
                            except Exception:
                                pass
                            def _http_get_json(url: str):
                                headers = dict(self.formulary_headers or {})
                                if self.formulary_cookie_header:
                                    headers['Cookie'] = self.formulary_cookie_header
                                attempts = 3
                                ssl_ctx = make_ssl_context()
                                for attempt in range(1, attempts + 1):
                                    try:
                                        req = urllib.request.Request(url, headers=headers)
                                        with urllib.request.urlopen(req, timeout=20, context=ssl_ctx) as resp:
                                            body = resp.read()
                                        return json.loads(body.decode('utf-8'))
                                    except Exception as exc:
                                        self.callbacks["capture_log"](
                                            f"HTTP fetch failed (attempt {attempt}/{attempts}): {exc}"
                                        )
                                        if attempt < attempts:
                                            try:
                                                self.callbacks["responsive_wait"](1.0 * attempt, label="HTTP retry")
                                            except Exception:
                                                time.sleep(1.0 * attempt)
                                return None
                            def collect_once(refresh: bool) -> bool:
                                nonlocal api_payloads
                                headers = dict(self.formulary_headers or {})
                                if self.formulary_cookie_header:
                                    headers["Cookie"] = self.formulary_cookie_header
                                if refresh:
                                    try:
                                        self.callbacks["capture_log"]("Refreshing page before capture.")
                                        page.reload(timeout=0, wait_until="domcontentloaded")
                                    except PlaywrightTimeoutError:
                                        self.callbacks["capture_log"]("Refresh timed out; using current content.")
                                    except Exception as exc:
                                        self.callbacks["capture_log"](f"Refresh error; using current content. ({exc})")
                                self.callbacks["capture_log"]("Page ready; collecting data.")
                                # Expand formulary pagination when only first page captured.
                                pagination_failed = False
                                total = None
                                data_list = []
                                try:
                                    base_payload = next((p for p in api_payloads if 'formulary-products' in (p.get('url') or '') and isinstance(p.get('data'), list)), None)
                                    if base_payload is None:
                                        def _extract_auth_token():
                                            for payload in api_payloads:
                                                if not isinstance(payload, dict):
                                                    continue
                                                req_headers = payload.get("request_headers") or {}
                                                token = req_headers.get("authorization") or req_headers.get("Authorization")
                                                if token:
                                                    return token
                                            for payload in api_payloads:
                                                url = payload.get("url") or ""
                                                data = payload.get("data")
                                                if "auth/initialize" in url and isinstance(data, dict):
                                                    tokens = data.get("tokens") or {}
                                                    access = tokens.get("accessToken")
                                                    if access:
                                                        return f"Bearer {access}"
                                            return None
                                        def _decode_jwt_payload(token: str) -> dict:
                                            try:
                                                raw = token.strip()
                                                if raw.lower().startswith("bearer "):
                                                    raw = raw[7:].strip()
                                                parts = raw.split(".")
                                                if len(parts) < 2:
                                                    return {}
                                                payload_b64 = parts[1]
                                                payload_b64 += "=" * (-len(payload_b64) % 4)
                                                decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
                                                return json.loads(decoded.decode("utf-8"))
                                            except Exception:
                                                return {}
                                        def _find_rpc_host() -> str | None:
                                            for payload in api_payloads:
                                                url = payload.get("url") or ""
                                                if "production-rpc-api" in url:
                                                    return urllib.parse.urlparse(url).netloc
                                            return None
                                        token = _extract_auth_token()
                                        rpc_host = _find_rpc_host()
                                        if token and rpc_host:
                                            jwt_payload = _decode_jwt_payload(token)
                                            patient_id = jwt_payload.get("roleEntityId")
                                            org_id = None
                                            ctx = jwt_payload.get("context") if isinstance(jwt_payload, dict) else None
                                            if isinstance(ctx, dict):
                                                org_id = ctx.get("organizationId")
                                            if patient_id and org_id:
                                                include_inactive = bool(self.cfg.get('include_inactive', False))
                                                requestable_only = bool(self.cfg.get('requestable_only', True))
                                                in_stock_only = bool(self.cfg.get('in_stock_only', False))
                                                base_url = (
                                                    f"https://{rpc_host}/formulary-products?"
                                                    f"patientId={patient_id}&pharmacyId={org_id}"
                                                    f"&productType=CANNABIS_PRODUCT&take=50&skip=0"
                                                    f"&includeInactive={'true' if include_inactive else 'false'}"
                                                    f"&requestableOnly={'true' if requestable_only else 'false'}"
                                                    f"&requireAvailableStock={'true' if in_stock_only else 'false'}"
                                                )
                                                headers = dict(headers)
                                                headers["authorization"] = token
                                                more = _http_get_json(base_url)
                                                if isinstance(more, list):
                                                    base_payload = {
                                                        "url": base_url,
                                                        "content_type": "application/json",
                                                        "kind": "list",
                                                        "count": len(more),
                                                        "data": more,
                                                        "request_headers": headers,
                                                        "cookie_header": self.formulary_cookie_header,
                                                    }
                                                    api_payloads.append(base_payload)
                                    base_url = None
                                    if base_payload:
                                        base_url = base_url or (base_payload.get('url') or '')
                                    if base_url and self.cfg.get('requestable_only') is not None:
                                        try:
                                            parsed = urllib.parse.urlparse(base_url)
                                            q = urllib.parse.parse_qs(parsed.query)
                                            include_inactive = bool(self.cfg.get('include_inactive', False))
                                            requestable_only = bool(self.cfg.get('requestable_only', True))
                                            in_stock_only = bool(self.cfg.get('in_stock_only', False))
                                            q['includeInactive'] = ['true' if include_inactive else 'false']
                                            q['requireAvailableStock'] = ['true' if in_stock_only else 'false']
                                            q['requestableOnly'] = ['true' if requestable_only else 'false']
                                            new_query = urllib.parse.urlencode(q, doseq=True)
                                            base_url = urllib.parse.urlunparse(parsed._replace(query=new_query))
                                            if base_url != (base_payload.get('url') or ''):
                                                more = _http_get_json(base_url)
                                                if more is None:
                                                    pagination_failed = True
                                            if isinstance(more, list):
                                                api_payloads.append({
                                                    "url": base_url,
                                                    "content_type": "application/json",
                                                    "kind": "list",
                                                    "count": len(more),
                                                    "data": more,
                                                    "request_headers": headers,
                                                    "cookie_header": self.formulary_cookie_header,
                                                })
                                        except Exception as exc:
                                            self.callbacks["capture_log"](f"Base formulary fetch failed: {exc}")
                                    count_payload = next((p for p in api_payloads if "formulary-products/count" in (p.get("url") or "") and isinstance(p.get("data"), dict)), None)
                                    if base_payload:
                                        base_url = base_url or (base_payload.get('url') or '')
                                        data_list = base_payload.get('data') or []
                                        # If we fetched a base list with override flags, prefer it.
                                        if base_url and base_url != (base_payload.get('url') or ''):
                                            try:
                                                data_list = next((p.get('data') for p in api_payloads if p.get('url') == base_url and isinstance(p.get('data'), list)), data_list)
                                            except Exception:
                                                pass
                                        take = 50
                                        try:
                                            take = int(urllib.parse.parse_qs(urllib.parse.urlparse(base_url).query).get('take', [take])[0])
                                        except Exception:
                                            pass
                                        total = None
                                        if base_url:
                                            try:
                                                parsed = urllib.parse.urlparse(base_url)
                                                q = urllib.parse.parse_qs(parsed.query)
                                                q.pop('take', None)
                                                q.pop('skip', None)
                                                count_path = parsed.path.replace('formulary-products', 'formulary-products/count')
                                                count_url = urllib.parse.urlunparse(parsed._replace(path=count_path, query=urllib.parse.urlencode(q, doseq=True)))
                                                count_resp = _http_get_json(count_url)
                                                if isinstance(count_resp, dict):
                                                    total = count_resp.get('count') or count_resp.get('total')
                                                    if total is not None:
                                                        self.callbacks["capture_log"](f"Count fetch status=200 total={total}")
                                            except Exception as exc:
                                                self.callbacks["capture_log"](f"Count fetch failed: {exc}")
                                        if count_payload and total is None:
                                            try:
                                                total = count_payload.get("data", {}).get("count")
                                                if total is None:
                                                    total = count_payload.get("data", {}).get("total")
                                            except Exception:
                                                total = None
                                        if total is None and isinstance(data_list, list):
                                            total = len(data_list)
                                        if total is not None:
                                            try:
                                                self.callbacks["capture_log"](f"Pagination: base={len(data_list)} total={total} take={take}")
                                            except Exception as exc:
                                                self._safe_log(f"Pagination log failed: {exc}")
                                        if total and isinstance(data_list, list) and len(data_list) < total:

                                            for skip in range(take, int(total), take):
                                                if self.callbacks["stop_event"].is_set():
                                                    break
                                                try:
                                                    parsed = urllib.parse.urlparse(base_url)
                                                    q = urllib.parse.parse_qs(parsed.query)
                                                    q['skip'] = [str(skip)]
                                                    q['take'] = [str(take)]
                                                    new_query = urllib.parse.urlencode(q, doseq=True)
                                                    next_url = urllib.parse.urlunparse(parsed._replace(query=new_query))
                                                    more = _http_get_json(next_url)
                                                    if more is None:
                                                        pagination_failed = True
                                                    if isinstance(more, list):
                                                        try:
                                                            self.callbacks["capture_log"](f"Pagination fetch skip={skip} status=200")
                                                        except Exception as exc:
                                                            self._safe_log(f"Pagination fetch log failed: {exc}")
                                                        api_payloads.append({
                                                            "url": next_url,
                                                            "content_type": "application/json",
                                                            "kind": "list",
                                                            "count": len(more),
                                                            "data": more,
                                                            "request_headers": headers,
                                                            "cookie_header": self.formulary_cookie_header,
                                                        })
                                                    else:
                                                        try:
                                                            self.callbacks["capture_log"](f"Pagination fetch skip={skip} status=error")
                                                        except Exception as exc:
                                                            self._safe_log(f"Pagination fetch log failed: {exc}")
                                                except Exception as exc:
                                                    self.callbacks["capture_log"](f"Pagination fetch failed: {exc}")
                                                    break
                                except Exception as exc:
                                    self._safe_log(f"Pagination handling failed: {exc}")
                                if not pagination_is_complete(data_list, total, pagination_failed):
                                    try:
                                        self.callbacks["capture_log"]("Pagination incomplete; skipping apply to avoid partial capture.")
                                    except Exception as exc:
                                        self._safe_log(f"Pagination incomplete log failed: {exc}")
                                    return False
                                # Filter captured payloads to the active filter combination to avoid duplicates.
                                try:
                                    include_inactive = bool(self.cfg.get('include_inactive', False))
                                    requestable_only = bool(self.cfg.get('requestable_only', True))
                                    in_stock_only = bool(self.cfg.get('in_stock_only', False))
                                    def _matches_filters(url: str) -> bool:
                                        try:
                                            parsed = urllib.parse.urlparse(url)
                                            if 'formulary-products' not in parsed.path:
                                                return True
                                            q = urllib.parse.parse_qs(parsed.query)
                                            def _q_bool(key: str, default: bool) -> bool:
                                                raw = q.get(key, [None])[0]
                                                if raw is None:
                                                    return default
                                                return str(raw).lower() == 'true'
                                            return (
                                                _q_bool('includeInactive', False) == include_inactive
                                                and _q_bool('requestableOnly', False) == requestable_only
                                                and _q_bool('requireAvailableStock', False) == in_stock_only
                                            )
                                        except Exception:
                                            return True
                                    filtered = []
                                    for payload in api_payloads:
                                        url = payload.get('url') or ''
                                        if not url or _matches_filters(url):
                                            filtered.append(payload)
                                    api_payloads = filtered
                                except Exception as exc:
                                    self._safe_log(f"Filter normalization failed: {exc}")
                                api_count = 0
                                for payload in api_payloads:
                                    try:
                                        data = payload.get("data")
                                        if isinstance(data, list) and data:
                                            if isinstance(data[0], dict) and ("product" in data[0] or "formularyId" in data[0]):
                                                api_count += len(data)
                                        elif isinstance(data, dict):
                                            items = data.get("items") or data.get("data") or data.get("results")
                                            if isinstance(items, list) and items:
                                                if isinstance(items[0], dict) and ("product" in items[0] or "formularyId" in items[0]):
                                                    api_count += len(items)
                                    except Exception:
                                        pass
                                if api_count <= 0:
                                    if api_payloads:
                                        try:
                                            urls = [p.get("url") for p in api_payloads[:5]]
                                            self.callbacks["capture_log"](f"No API list data found. Sample URLs: {urls}")
                                        except Exception as exc:
                                            self._safe_log(f"Sample URL log failed: {exc}")
                                    else:
                                        if xhr_urls:
                                            sample = list(dict.fromkeys(xhr_urls))[:5]
                                            self.callbacks["capture_log"](f"No API JSON decoded. Sample XHR: {sample}")
                                        else:
                                            self.callbacks["capture_log"]("No API responses captured yet.")
                                    return False
                                self.empty_failures = 0
                                dump_dir = None
                                stamp = None
                                try:
                                    dump_dir = Path(self.app_dir) / "data"
                                    dump_dir.mkdir(parents=True, exist_ok=True)
                                except Exception:
                                    dump_dir = None
                                if self.cfg.get("dump_capture_html") or self.cfg.get("dump_api_json"):
                                    stamp = time.strftime("%Y%m%d_%H%M%S")
                                if dump_dir:
                                    if not api_payloads:
                                        self.callbacks["capture_log"]("No API JSON responses captured.")
                                    else:
                                        self._persist_auth_cache(api_payloads)
                                        try:
                                            latest_path = dump_dir / "api_latest.json"
                                            latest_path.write_text(json.dumps(api_payloads, ensure_ascii=False, indent=2), encoding="utf-8")
                                        except Exception as exc:
                                            self.callbacks["capture_log"](f"API latest write failed: {exc}")
                                        if endpoint_summaries and stamp:
                                            try:
                                                summary_path = dump_dir / f"api_endpoints_{stamp}.json"
                                                summary_path.write_text(json.dumps(endpoint_summaries, ensure_ascii=False, indent=2), encoding="utf-8")
                                                self.callbacks["capture_log"](f"Saved API endpoint summary: {summary_path}")
                                            except Exception as exc:
                                                self.callbacks["capture_log"](f"API endpoint summary failed: {exc}")
                                        if self.cfg.get("dump_api_json") and stamp:
                                            try:
                                                summary_path = dump_dir / f"api_endpoints_{stamp}.json"
                                                summary_path.write_text(json.dumps(endpoint_summaries, ensure_ascii=False, indent=2), encoding="utf-8")
                                                self.callbacks["capture_log"](f"Saved API endpoint summary: {summary_path}")
                                            except Exception as exc:
                                                self.callbacks["capture_log"](f"API endpoint summary failed: {exc}")
                                            try:
                                                api_path = dump_dir / f"api_dump_{stamp}.json"
                                                api_path.write_text(json.dumps(api_payloads, ensure_ascii=False, indent=2), encoding="utf-8")
                                                self.callbacks["capture_log"](f"Saved API dump: {api_path}")
                                            except Exception as exc:
                                                self.callbacks["capture_log"](f"API dump failed: {exc}")
                                if self.cfg.get("dump_capture_html") and dump_dir and stamp:
                                    try:
                                        html_path = dump_dir / f"page_dump_{stamp}.html"
                                        html_path.write_text(page.content(), encoding="utf-8")
                                        self.callbacks["capture_log"](f"Saved page HTML: {html_path}")
                                    except Exception as exc:
                                        self.callbacks["capture_log"](f"HTML dump failed: {exc}")
                                try:
                                    self.callbacks["apply_text"]("")
                                except Exception as exc:
                                    self._safe_log(f"Apply text callback failed: {exc}")
                                return True

                            # First attempt: no refresh, assume page loaded during waits.
                            success = collect_once(refresh=False)
                            attempt_wait = self.retry_policy.retry_wait_seconds
                            attempt = 0
                            while not success and retries_left > 0 and not self.callbacks["stop_event"].is_set():
                                retries_left -= 1
                                attempt += 1
                                self.callbacks["capture_log"](
                                    f"No content; retrying after {attempt_wait}s (attempt {attempt}/{self.retry_policy.retry_attempts})."
                                )
                                if self.callbacks["responsive_wait"](attempt_wait, label="Retrying capture"):
                                    break
                                # Sequence: retry 1 re-check without refresh; retry 2 refresh; retry 3 re-check without refresh.
                                refresh_flag = attempt == 2
                                success = collect_once(refresh=refresh_flag)
                            if not success:
                                self.empty_failures += 1
                                if self.empty_failures == 1:
                                    self._backoff_logged_for = 0
                                self._set_status("retrying", "Empty page content; restarting browser.")
                                restart_browser = True
                                break
                            first_cycle = False
                        except PlaywrightTimeoutError:
                            self._set_status("retrying", "Navigation timed out; will retry.")
                        except Exception as exc:
                            self._set_status("retrying", f"Capture error: {exc}")
                        # Overnight slow-down
                        interval = self.scheduler.next_interval(self.cfg["interval_seconds"], self.cfg)
                        if self.empty_failures:
                            interval = self.retry_policy.interval_with_backoff(interval, self.empty_failures)
                            if self.empty_failures > self._backoff_logged_for:
                                self._backoff_logged_for = self.empty_failures
                                if (self.empty_failures % self._BACKOFF_LOG_EVERY) == 0:
                                    try:
                                        self.callbacks["capture_log"](
                                            f"Capture backoff active: failures={self.empty_failures} next_interval={interval:.1f}s"
                                        )
                                    except Exception:
                                        self._safe_log("API count scan failed.")
                        if self.scheduler.wait(interval, label="Waiting for next capture"):
                            break
                    try:
                        browser.close()
                    except Exception:
                        pass
                    if not restart_browser:
                        self._set_status("stopped")
                        break
        except Exception as exc:
            self._set_status("faulted", f"Auto-capture error: {exc}")
        finally:
            self.callbacks["stop_event"].set()
            on_stop = self.callbacks.get("on_stop")
            if on_stop:
                try:
                    on_stop()
                except Exception:
                    try:
                        self.callbacks.get("capture_log", lambda m: None)(
                            "Capture on_stop callback failed."
                        )
                    except Exception:
                        pass


def ensure_playwright_installed(app_dir: Path, log: Callable[[str], None]) -> Optional[tuple]:
    """Ensure playwright is importable and browsers are installed; returns (sync_playwright, TimeoutError) or None."""
    global _Playwright
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # type: ignore
    except Exception as exc:
        log(f"Playwright not installed: {exc}")
        return None
    _Playwright = (sync_playwright, PlaywrightTimeoutError)
    return _Playwright


def ensure_browser_available(app_dir: Path, log: Callable[[str], None], install_cb: Optional[Callable[[], bool]] = None) -> Optional[tuple]:
    """
    Ensure Playwright and browser are available.
    Returns (sync_playwright, TimeoutError) or None on failure after attempts.
    """
    req = ensure_playwright_installed(app_dir, log)
    if req:
        return req
    if install_cb:
        log("Playwright not installed; attempting browser install...")
        ok = install_cb()
        if ok:
            return ensure_playwright_installed(app_dir, log)
    return None


def install_playwright_browsers(app_dir: Path, log: Callable[[str], None]) -> bool:
    """Attempt to download Playwright Chromium browsers."""
    try:
        log("Downloading Playwright browser (this may take a minute)...")
        import playwright.__main__ as pw_main  # type: ignore

        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(app_dir / "pw-browsers"))
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = env_path
        prev_argv = list(sys.argv)
        sys.argv = ["playwright", "install", "chromium"]
        try:
            pw_main.main()
        finally:
            sys.argv = prev_argv
        log(f"Playwright browser installed to {env_path}.")
        return True
    except Exception as exc:
        log(f"Playwright install failed: {exc}")
        return False


def start_capture_worker(
    cfg: dict,
    callbacks: CaptureCallbacks,
    app_dir: Optional[Path] = None,
    install_fn: Optional[Callable[[], bool]] = None,
) -> threading.Thread:
    """
    Start the capture worker thread.
    cfg keys: url, interval_seconds, login_wait_seconds, post_nav_wait_seconds, username, password, selectors, headless, minimize_to_tray, close_to_tray
    callbacks keys: log, capture_log, apply_text, update_tray, on_stop, on_error, on_done
    """
    worker = CaptureWorker(cfg, callbacks, app_dir, install_fn)
    return worker.start()


class IntervalScheduler:
    """Handles wait intervals with optional overnight backoff and stop checks."""

    def __init__(self, stop_event: Event, wait_fn: Callable[[float, str], bool]) -> None:
        self.stop_event: Event = stop_event
        self.wait_fn: Callable[[float, str], bool] = wait_fn

    def next_interval(self, base_interval: float, cfg: dict) -> float:
        """Return the next interval, honoring quiet-hours override when enabled."""
        interval = base_interval
        try:
            if not cfg.get("quiet_hours_enabled"):
                return interval
            quiet_interval = float(cfg.get("quiet_hours_interval_seconds", interval) or interval)
            if quiet_interval <= 0:
                quiet_interval = interval
            start = _parse_time(cfg.get("quiet_hours_start"))
            end = _parse_time(cfg.get("quiet_hours_end"))
            now = datetime.now().time()
            if _in_window(now, start, end):
                interval = quiet_interval
        except Exception:
            pass
        return interval

    def wait(self, seconds: float, label: str) -> bool:
        """Wait using the provided wait_fn (returns True if stop requested)."""
        return self.wait_fn(seconds, label=label)


def _parse_time(value: str | None):
    if not value:
        return None
    try:
        parts = [int(p) for p in str(value).strip().split(":")[:2]]
        if len(parts) != 2:
            return None
        hour, minute = parts
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return None
        return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0).time()
    except Exception:
        return None


def _in_window(now, start, end) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now < end
    # Overnight window (e.g. 22:00 -> 07:00)
    return now >= start or now < end
