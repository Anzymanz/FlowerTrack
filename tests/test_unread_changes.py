from __future__ import annotations

from unread_changes import (
    clear_unread_changes,
    load_unread_changes,
    merge_unread_changes,
    unread_payload,
    unread_removed_items_for_export,
)


def _item(product_id: str, *, strain: str = "Example", producer: str = "Brand", price: float = 10.0) -> dict:
    return {
        "product_id": product_id,
        "producer": producer,
        "brand": producer,
        "strain": strain,
        "product_type": "flower",
        "price": price,
        "stock": "IN STOCK",
        "stock_remaining": 10,
    }


def test_merge_unread_changes_sets_flags_and_removed_snapshot(tmp_path):
    path = tmp_path / "unread.json"
    cur = _item("A1", strain="New Flower", price=12.0)
    rem = _item("B2", strain="Removed Flower", price=8.0)
    diff = {
        "new_items": [cur],
        "removed_items": [rem],
        "price_changes": [{**cur, "price_delta": 1.0}],
        "stock_changes": [{**cur, "stock_delta": -1.0}],
        "out_of_stock_changes": [],
        "restock_changes": [],
    }
    changed = merge_unread_changes(diff, [cur], path)
    assert changed is True

    state = load_unread_changes(path)
    assert state["epoch"] >= 1
    assert state["items"]
    assert state["removed_items"]

    payload = unread_payload(path)
    assert payload["items"]
    one_entry = next(iter(payload["items"].values()))
    assert one_entry.get("new") is True
    assert one_entry.get("price") is True
    assert one_entry.get("stock") is True

    removed = unread_removed_items_for_export([cur], path)
    assert len(removed) == 1
    assert removed[0].get("is_removed") is True


def test_unread_removed_snapshot_clears_when_item_returns(tmp_path):
    path = tmp_path / "unread.json"
    rem = _item("B2", strain="Removed Flower", price=8.0)
    diff_removed = {
        "new_items": [],
        "removed_items": [rem],
        "price_changes": [],
        "stock_changes": [],
        "out_of_stock_changes": [],
        "restock_changes": [],
    }
    merge_unread_changes(diff_removed, [], path)
    state_before = load_unread_changes(path)
    assert state_before["removed_items"]

    # Item is present again in current parse; removed snapshot should be dropped.
    merge_unread_changes(
        {
            "new_items": [],
            "removed_items": [],
            "price_changes": [],
            "stock_changes": [],
            "out_of_stock_changes": [],
            "restock_changes": [],
        },
        [rem],
        path,
    )
    state_after = load_unread_changes(path)
    assert not state_after["removed_items"]


def test_clear_unread_changes(tmp_path):
    path = tmp_path / "unread.json"
    cur = _item("A1")
    merge_unread_changes(
        {
            "new_items": [cur],
            "removed_items": [],
            "price_changes": [],
            "stock_changes": [],
            "out_of_stock_changes": [],
            "restock_changes": [],
        },
        [cur],
        path,
    )
    assert clear_unread_changes(path) is True
    state = load_unread_changes(path)
    assert state["items"] == {}
    assert state["removed_items"] == {}

