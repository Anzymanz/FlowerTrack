from __future__ import annotations
from typing import Any
from parser import make_identity_key


def _identity_key_cached(item: dict, cache: dict) -> str:
    key = id(item)
    cached = cache.get(key)
    if cached is None:
        cached = make_identity_key(item)
        cache[key] = cached
    return cached


def _build_identity_cache(items: list[dict]) -> dict:
    cache: dict[int, str] = {}
    for it in items:
        cache[id(it)] = make_identity_key(it)
    return cache


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _stock_is_out(stock, remaining) -> bool:
    if remaining is not None:
        try:
            return float(remaining) <= 0
        except Exception:
            pass
    text = str(stock or '').upper()
    return 'OUT' in text


def _stock_is_in(stock, remaining) -> bool:
    if remaining is not None:
        try:
            return float(remaining) > 0
        except Exception:
            pass
    text = str(stock or '').upper()
    return ('IN STOCK' in text) or ('LOW STOCK' in text) or ('REMAINING' in text)


def compute_diffs(current_items: list[dict], prev_items: list[dict]) -> dict:
    identity_cache = _build_identity_cache(current_items + prev_items)
    current_keys = {_identity_key_cached(it, identity_cache) for it in current_items}
    prev_keys = {_identity_key_cached(it, identity_cache) for it in prev_items}
    new_keys = current_keys - prev_keys
    removed_keys = prev_keys - current_keys

    new_items: list[dict] = []
    for it in current_items:
        key = _identity_key_cached(it, identity_cache)
        is_new = key in new_keys
        it["is_new"] = bool(is_new)
        it["is_removed"] = False
        if is_new:
            new_items.append(it)

    removed_items = [
        dict(it, is_removed=True, is_new=False)
        for it in prev_items
        if _identity_key_cached(it, identity_cache) in removed_keys
    ]

    prev_price_map: dict[str, float | None] = {}
    prev_stock_map: dict[str, Any] = {}
    prev_remaining_map: dict[str, Any] = {}
    prev_item_map: dict[str, dict] = {}
    for pit in prev_items:
        key = _identity_key_cached(pit, identity_cache)
        prev_item_map[key] = pit
        prev_price_map[key] = _coerce_float(pit.get("price"))
        prev_stock_map[key] = pit.get("stock")
        prev_remaining_map[key] = pit.get("stock_remaining")

    price_changes: list[dict] = []
    stock_changes: list[dict] = []
    restock_changes: list[dict] = []
    out_of_stock_changes: list[dict] = []
    price_up = 0
    price_down = 0
    stock_change_count = 0

    for it in current_items:
        key = _identity_key_cached(it, identity_cache)
        prev_price = prev_price_map.get(key)
        cur_price = _coerce_float(it.get("price"))
        if cur_price is not None and prev_price is not None and cur_price != prev_price:
            delta = cur_price - prev_price
            it["price_delta"] = delta
            price_changes.append({
                **it,
                "price_delta": delta,
                "price_before": prev_price,
                "price_after": cur_price,
            })
            if delta > 0:
                price_up += 1
            elif delta < 0:
                price_down += 1
        else:
            if "price_delta" in it:
                del it["price_delta"]

        prev_stock = prev_stock_map.get(key)
        prev_rem = prev_remaining_map.get(key)
        cur_stock = it.get("stock")
        cur_rem = it.get("stock_remaining")

        stock_delta = None
        if prev_rem is not None or cur_rem is not None:
            try:
                stock_delta = float(cur_rem) - float(prev_rem)
            except Exception:
                stock_delta = None
        if stock_delta is not None and abs(stock_delta) < 1e-6:
            stock_delta = 0.0
        if stock_delta is not None:
            it["stock_delta"] = stock_delta
        else:
            if "stock_delta" in it:
                del it["stock_delta"]

        prev_out = _stock_is_out(prev_stock, prev_rem)
        cur_out = _stock_is_out(cur_stock, cur_rem)
        prev_in = _stock_is_in(prev_stock, prev_rem)
        cur_in = _stock_is_in(cur_stock, cur_rem)
        is_restock = prev_out and cur_in
        it["is_restock"] = bool(is_restock)

        if is_restock:
            if stock_delta is None:
                it["stock_delta"] = 1.0
            restock_changes.append({
                **it,
                "stock_before": prev_stock,
                "stock_after": cur_stock,
            })
            stock_change_count += 1
            continue
        if prev_in and cur_out:
            if stock_delta is None:
                it["stock_delta"] = -1.0
            out_of_stock_changes.append({
                **it,
                "stock_before": prev_stock,
                "stock_after": cur_stock,
            })
            stock_change_count += 1
            continue

        stock_change_entry = None
        if prev_stock is not None and cur_stock is not None and str(prev_stock) != str(cur_stock):
            stock_change_entry = {
                **it,
                "stock_before": prev_stock,
                "stock_after": cur_stock,
            }
        elif (prev_rem is not None or cur_rem is not None) and prev_rem != cur_rem:
            stock_change_entry = {
                **it,
                "stock_before": prev_rem,
                "stock_after": cur_rem,
            }
        if stock_change_entry is not None:
            stock_changes.append(stock_change_entry)
            stock_change_count += 1

    return {
        "new_items": new_items,
        "removed_items": removed_items,
        "price_changes": price_changes,
        "stock_changes": stock_changes,
        "restock_changes": restock_changes,
        "out_of_stock_changes": out_of_stock_changes,
        "price_up": price_up,
        "price_down": price_down,
        "stock_change_count": stock_change_count,
        "current_keys": current_keys,
        "prev_keys": prev_keys,
    }
