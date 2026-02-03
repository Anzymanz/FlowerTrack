import json
import re
import urllib.parse
from typing import Iterable, Any
from models import ItemDict

def _normalize_val(val):
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val).strip().lower()

def make_item_key(item: dict) -> str:
    """Stable key to identify a product across parses."""
    parts = [
        _normalize_val(item.get("product_id")),
        _normalize_val(item.get("producer")),
        _normalize_val(item.get("brand")),
        _normalize_val(item.get("strain")),
        _normalize_val(item.get("grams")),
        _normalize_val(item.get("ml")),
        _normalize_val(item.get("price")),
        _normalize_val(item.get("product_type")),
        _normalize_val(item.get("strain_type")),
    ]
    return "|".join(parts)

def make_identity_key(item: dict) -> str:
    """Identity key that ignores price so price changes don't look like new items."""
    parts = [
        _normalize_val(item.get("product_id")),
        _normalize_val(item.get("producer")),
        _normalize_val(item.get("brand")),
        _normalize_val(item.get("strain")),
        _normalize_val(item.get("grams")),
        _normalize_val(item.get("ml")),
        _normalize_val(item.get("product_type")),
        _normalize_val(item.get("strain_type")),
        _normalize_val(item.get("is_smalls")),
        _normalize_val(item.get("thc")),
        _normalize_val(item.get("thc_unit")),
        _normalize_val(item.get("cbd")),
        _normalize_val(item.get("cbd_unit")),
    ]
    return "|".join(parts)

def get_google_medicann_link(producer: str | None, strain: str | None) -> str:
    parts = [producer.strip() if producer else "", strain.strip() if strain else ""]
    q = " ".join([p for p in parts if p]) + " medbud.wiki"
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)

def _normalize_strain_type(raw: str | None) -> str | None:
    if not raw:
        return None
    upper = str(raw).upper()
    if "SATIVA" in upper:
        return "Sativa"
    if "INDICA" in upper:
        return "Indica"
    if "HYBRID" in upper:
        return "Hybrid"
    return None

def _normalize_product_type(raw: str | None) -> str | None:
    if not raw:
        return None
    upper = str(raw).upper()
    if "FLOWER" in upper:
        return "flower"
    if "OIL" in upper:
        return "oil"
    if "VAPE" in upper or "CARTRIDGE" in upper:
        return "vape"
    if "DEVICE" in upper:
        return "device"
    return None

def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None

def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None

def _clean_title(value: str | None) -> str | None:
    if not value:
        return value
    out = str(value).strip()
    out = re.sub(r"\s*-\s*(FLOWER|OIL|VAPE|DEVICE|CARTRIDGE)\b", "", out, flags=re.I)
    out = re.sub(r"\s+", " ", out).strip()
    return out

def _parse_formulary_item(entry: dict) -> ItemDict | None:
    if not isinstance(entry, dict):
        return None
    product = entry.get("product") or {}
    cannabis = product.get("cannabisSpecification") or {}
    specs = entry.get("specifications") or product.get("specifications") or {}
    metadata = product.get("metadata") or {}
    raw_name = entry.get("name") or product.get("name") or ""
    long_name = raw_name or (metadata.get("name") if isinstance(metadata, dict) else None) or ""
    name = _clean_title(raw_name) or raw_name
    if not name or str(name).strip().upper() in {"UNKNOWN", "N/A", "NA"}:
        fallback = _clean_title(long_name) or long_name
        name = fallback or name
    is_smalls = bool(re.search(r"\b(SMALLS?|SMALL BUDS?|MINI(S)?)\b", raw_name, re.I))
    external_ref = entry.get("externalReference") or specs.get("externalId") or metadata.get("externalId")
    product_id = external_ref or (str(entry.get("productId")) if entry.get("productId") is not None else None)
    brand = (product.get("brand") or {}).get("name") or metadata.get("brandName") or None
    brand_logo_url = None
    brand_obj = product.get("brand") or {}
    if isinstance(brand_obj, dict):
        brand_logo_url = brand_obj.get("logoUrl") or brand_obj.get("logo_url")
    image_url = entry.get("mainImageUrl") or product.get("mainImageUrl")
    strain = cannabis.get("strainName") or metadata.get("strain")
    if not strain or str(strain).strip().upper() in {"N/A", "NA", "NONE", "UNKNOWN"}:
        strain = name
    strain_type = _normalize_strain_type(cannabis.get("strainType") or metadata.get("classification"))
    irradiation = cannabis.get("irradiationType") or specs.get("irradiationType") or metadata.get("irradiationType")
    origin_country = (
        product.get("originCountry")
        or specs.get("originCountry")
        or metadata.get("originCountry")
    )
    product_type = (
        _normalize_product_type(cannabis.get("format"))
        or _normalize_product_type(metadata.get("oldProductType"))
        or _normalize_product_type(product.get("type"))
        or _normalize_product_type(name)
    )
    grams = None
    ml = None
    size = _coerce_float(cannabis.get("size") or specs.get("size"))
    unit = (cannabis.get("volumeUnit") or specs.get("volumeUnit") or metadata.get("units") or "").upper()
    if size is not None:
        if unit == "GRAMS":
            grams = size
        elif unit in ("ML", "MILLILITERS", "MILLILITRES"):
            ml = size
    thc = _coerce_float(cannabis.get("thcContent") or specs.get("thcContent"))
    cbd = _coerce_float(cannabis.get("cbdContent") or specs.get("cbdContent"))
    thc_unit = "%" if thc is not None else None
    cbd_unit = "%" if cbd is not None else None
    pricing = entry.get("pricingOptions")
    price = None
    availability = None
    on_order = bool(entry.get("onOrder"))
    if isinstance(pricing, dict) and pricing:
        opt = pricing.get("STANDARD") or next(iter(pricing.values()))
        price = _coerce_float(opt.get("price") if isinstance(opt, dict) else None)
        availability = _coerce_int(opt.get("totalAvailability") if isinstance(opt, dict) else None)
    elif isinstance(pricing, list) and pricing:
        opt = pricing[0]
        if isinstance(opt, dict):
            price = _coerce_float(opt.get("price"))
            availability = _coerce_int(opt.get("totalAvailability"))
    stock_status = None
    stock_detail = None
    if availability is not None:
        if availability <= 0:
            stock_status = "OUT OF STOCK"
        elif availability <= 10:
            stock_status = "LOW STOCK"
            stock_detail = f"{availability} remaining"
        else:
            stock_status = "IN STOCK"
    stock = stock_detail or stock_status
    unknown_name = False
    if name is None:
        unknown_name = True
    else:
        upper_name = str(name).strip().upper()
        if not upper_name or upper_name in {"UNKNOWN", "N/A", "NA"}:
            unknown_name = True
    if unknown_name:
        if (availability is not None and availability >= 1000) or (price is not None and price <= 0):
            return None
    if name and (
        'NOT PRESCRIBABLE' in str(name).upper()
        or 'FORMULATION ONLY' in str(name).upper()
    ):
        return None
    item: ItemDict = {
        "product_id": product_id,
        "title": name,
        "producer": brand,
        "brand": brand,
        "strain": strain,
        "strain_type": strain_type,
        "irradiation_type": irradiation,
        "origin_country": origin_country,
        "stock": stock,
        "stock_status": stock_status,
        "stock_detail": stock_detail,
        "stock_remaining": availability,
        "product_type": product_type or "flower",
        "is_smalls": is_smalls,
        "grams": grams,
        "ml": ml,
        "price": price,
        "thc": thc,
        "thc_unit": thc_unit,
        "cbd": cbd,
        "cbd_unit": cbd_unit,
        "image_url": image_url,
        "brand_logo_url": brand_logo_url,
    }
    return item

def parse_api_payloads(payloads: Iterable[dict]) -> list[ItemDict]:
    items_by_key: dict[str, ItemDict] = {}
    for payload in payloads or []:
        if not isinstance(payload, dict):
            continue
        url = payload.get("url") or ""
        data = payload.get("data")
        if "formulary-products" not in url:
            continue
        if isinstance(data, dict):
            data = data.get("items") or data.get("data") or data.get("results")
        if not isinstance(data, list):
            continue
        for entry in data:
            parsed = _parse_formulary_item(entry)
            if not parsed:
                continue
            pid = parsed.get("product_id")
            if pid:
                key = f"id:{pid}"
            else:
                key = f"name:{parsed.get('title') or ''}|brand:{parsed.get('brand') or ''}|g:{parsed.get('grams') or ''}|ml:{parsed.get('ml') or ''}"
            existing = items_by_key.get(key)
            if not existing:
                items_by_key[key] = parsed
                continue
            try:
                new_price = float(parsed.get("price")) if parsed.get("price") is not None else None
            except Exception:
                new_price = None
            try:
                old_price = float(existing.get("price")) if existing.get("price") is not None else None
            except Exception:
                old_price = None
            replace = False
            new_stock = parsed.get("stock_remaining")
            old_stock = existing.get("stock_remaining")
            if isinstance(new_stock, (int, float)) and not isinstance(old_stock, (int, float)):
                replace = True
            elif isinstance(new_stock, (int, float)) and isinstance(old_stock, (int, float)) and new_stock > old_stock:
                replace = True
            elif isinstance(new_stock, (int, float)) and isinstance(old_stock, (int, float)) and new_stock == old_stock:
                if new_price is not None and (old_price is None or new_price < old_price):
                    replace = True
            if replace:
                items_by_key[key] = parsed
    return list(items_by_key.values())

