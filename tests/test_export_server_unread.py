import json
import os
import socket
from pathlib import Path
from urllib import request

from export_server import start_export_server, stop_export_server
from unread_changes import merge_unread_changes


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _item(product_id: str) -> dict:
    return {
        "product_id": product_id,
        "producer": "Brand",
        "brand": "Brand",
        "strain": "Example",
        "product_type": "flower",
        "price": 10.0,
        "stock": "IN STOCK",
        "stock_remaining": 10,
    }


def _json_get(url: str) -> dict:
    with request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _json_post(url: str) -> dict:
    req = request.Request(url, method="POST", data=b"")
    with request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_unread_endpoints_ack_and_clear(tmp_path):
    appdata = Path(tmp_path)
    exports_dir = appdata / "FlowerTrack" / "Exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    old_appdata = os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(appdata)
    httpd = None
    thread = None
    try:
        merge_unread_changes(
            {
                "new_items": [_item("A1")],
                "removed_items": [],
                "price_changes": [],
                "stock_changes": [],
                "out_of_stock_changes": [],
                "restock_changes": [],
            },
            [_item("A1")],
        )
        httpd, thread, port = start_export_server(_free_port(), exports_dir, lambda _m: None)
        assert port

        unread_before = _json_get(f"http://127.0.0.1:{port}/api/changes/unread")
        assert unread_before.get("items")

        ack = _json_post(f"http://127.0.0.1:{port}/api/changes/ack")
        assert ack.get("acknowledged") is True
        assert ack.get("had_changes") is True
        assert ack.get("items") == {}

        unread_after = _json_get(f"http://127.0.0.1:{port}/api/changes/unread")
        assert unread_after.get("items") == {}
    finally:
        stop_export_server(httpd, thread, lambda _m: None)
        if old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = old_appdata


def test_unread_ack_reports_no_changes_when_empty(tmp_path):
    appdata = Path(tmp_path)
    exports_dir = appdata / "FlowerTrack" / "Exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    old_appdata = os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(appdata)
    httpd = None
    thread = None
    try:
        httpd, thread, port = start_export_server(_free_port(), exports_dir, lambda _m: None)
        assert port

        ack = _json_post(f"http://127.0.0.1:{port}/api/changes/ack")
        assert ack.get("acknowledged") is True
        assert ack.get("had_changes") is False
        assert ack.get("items") == {}
    finally:
        stop_export_server(httpd, thread, lambda _m: None)
        if old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = old_appdata
