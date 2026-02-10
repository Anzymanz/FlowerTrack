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

def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"true", "1", "yes", "y", "on"}:
            return True
        if raw in {"false", "0", "no", "n", "off"}:
            return False
    return None

def _clean_title(value: str | None) -> str | None:
    if not value:
        return value
    out = str(value).strip()
    out = re.sub(r"\s*-\s*(FLOWER|OIL|VAPE|DEVICE|CARTRIDGE)\b", "", out, flags=re.I)
    out = re.sub(r"\s*\([^)]*(THC|CBD|%)[^)]*\)\s*$", "", out, flags=re.I)
    out = re.sub(r"\s*\([^)]*$", "", out)
    out = re.sub(r"\s*[\(\[\{]+$", "", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out

def _is_useful_oil_base_name(value: str | None) -> bool:
    if not value:
        return False
    raw = re.sub(r"\s+", " ", str(value)).strip()
    if not raw:
        return False
    norm = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    # Generic placeholders should not be preserved in title composition.
    generic = {
        "oil",
        "cannabis oil",
        "medical cannabis oil",
        "thc medical cannabis oil",
        "sublingual oil",
        "cannabis sublingual oil",
        "cannabis oral oil",
        "oral oil",
    }
    if norm in generic:
        return False
    return True

def _extract_oil_base_name(value: str | None) -> str | None:
    if not value:
        return None
    out = str(value).strip()
    # Remove potency/ratio and concentration fragments.
    out = re.sub(r"\bT\s*\d{1,3}\s*:\s*C\s*\d{1,3}\b", "", out, flags=re.I)
    out = re.sub(r"\bT\s*\d{1,3}\b", "", out, flags=re.I)
    out = re.sub(r"\bTHC\s*[<>=~≤≥]?\s*\d{1,3}(?:\.\d+)?\s*MG\s*/\s*ML\b", "", out, flags=re.I)
    out = re.sub(r"\bCBD\s*[<>=~≤≥]?\s*\d{1,3}(?:\.\d+)?\s*MG\s*/\s*ML\b", "", out, flags=re.I)
    out = re.sub(r"\bTHC\s*:?\s*\d{1,3}\s*%?\b", "", out, flags=re.I)
    out = re.sub(r"\bCBD\s*:?\s*\d{1,3}\s*%?\b", "", out, flags=re.I)
    # Remove size and generic oil wording.
    out = re.sub(r"\b\d+(?:\.\d+)?\s*ML\b", "", out, flags=re.I)
    out = re.sub(r"\bMEDICAL\s+CANNABIS\b", "", out, flags=re.I)
    out = re.sub(r"\bCANNABIS\s+SUBLINGUAL\s+OIL\b", "", out, flags=re.I)
    out = re.sub(r"\bCANNABIS\s+OIL\b", "", out, flags=re.I)
    out = re.sub(r"\bSUBLINGUAL\s+OIL\b", "", out, flags=re.I)
    out = re.sub(r"\bORAL\s+OIL\b", "", out, flags=re.I)
    out = re.sub(r"\bOIL\b", "", out, flags=re.I)
    out = re.sub(r"[\(\)\[\],]+", " ", out)
    out = re.sub(r"\s+", " ", out).strip(" -:")
    tokens = []
    for tok in out.split():
        up = tok.upper()
        if up in {"THC", "CBD", "MG", "ML", "S"}:
            continue
        if re.fullmatch(r"[<>=~≤≥]?\d+(?:\.\d+)?", tok):
            continue
        if re.search(r"MG\s*/\s*ML", tok, flags=re.I):
            continue
        tokens.append(tok)
    out = " ".join(tokens).strip(" -:")
    if not out:
        return None
    # Use a friendlier display case for residual base names.
    return out.title()

def _canonical_oil_name(raw_name: str, thc: float | None, cbd: float | None) -> str | None:
    upper = str(raw_name or "").upper()
    if not upper:
        return None
    if "BALANCE" in upper:
        ratio_match = re.search(r"\bT\s*(\d{1,3})\s*:\s*C\s*(\d{1,3})\b", upper)
        if ratio_match:
            t_val = int(ratio_match.group(1))
            c_val = int(ratio_match.group(2))
            return f"Balance T{t_val}C{c_val} Sublingual Oil"
        if thc is not None and cbd is not None:
            t_val = int(round(thc))
            c_val = int(round(cbd))
            if c_val > 0:
                return f"Balance T{t_val}C{c_val} Sublingual Oil"
        return "Balance Sublingual Oil"

    profile = None
    code_match = re.search(r"\bT\s*(\d{1,3})(?:\s*:\s*C\s*(\d{1,3}))?\b", upper)
    if code_match:
        thc_code = code_match.group(1)
        cbd_code = code_match.group(2)
        if cbd_code:
            profile = f"T{int(thc_code)}C{int(cbd_code)}"
        else:
            profile = f"T{int(thc_code)}"
    elif thc is not None:
        thc_i = int(round(thc))
        cbd_i = int(round(cbd)) if cbd is not None else 0
        # Keep ratio naming for clearly mixed oils; otherwise keep a simple THC profile.
        if cbd_i >= 10:
            profile = f"T{thc_i}C{cbd_i}"
        else:
            profile = f"T{thc_i}"

    if not profile:
        return None
    return f"{profile} Sublingual Oil"

def _parse_formulary_item(entry: dict) -> ItemDict | None:
    if not isinstance(entry, dict):
        return None
    product = entry.get("product") or {}
    cannabis = product.get("cannabisSpecification") or {}
    specs = entry.get("specifications") or product.get("specifications") or {}
    metadata = product.get("metadata") or {}
    raw_name = entry.get("name") or product.get("name") or entry.get("title") or product.get("title") or ""
    product_name = product.get("name") or product.get("title") or ""
    long_name = (
        raw_name
        or product_name
        or (metadata.get("name") if isinstance(metadata, dict) else None)
        or (metadata.get("title") if isinstance(metadata, dict) else None)
        or ""
    )
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
    if product_type in {"oil", "vape"} and long_name:
        source_name = product_name if (product_type == "vape" and product_name) else long_name
        long_clean = _clean_title(source_name) or source_name
        if long_clean:
            name = long_clean
    strain = cannabis.get("strainName") or metadata.get("strain")
    if not strain or str(strain).strip().upper() in {"N/A", "NA", "NONE", "UNKNOWN", "-", "--"}:
        strain = name
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
    if product_type == "oil":
        canonical_name = _canonical_oil_name(raw_name, thc, cbd)
        if canonical_name:
            base_name = _extract_oil_base_name(name) or _extract_oil_base_name(raw_name) or _clean_title(name) or name
            if _is_useful_oil_base_name(base_name):
                base_upper = str(base_name).upper()
                canon_upper = str(canonical_name).upper()
                if canon_upper in base_upper:
                    composed = base_name
                else:
                    composed = f"{base_name} - {canonical_name}"
            else:
                composed = canonical_name
            name = composed
            strain = composed
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
        elif availability < 15:
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
    status = entry.get("status") or product.get("status") or metadata.get("status")
    requestable = _coerce_bool(
        entry.get("requestable")
        or entry.get("isRequestable")
        or product.get("requestable")
        or product.get("isRequestable")
        or metadata.get("requestable")
    )
    is_active = _coerce_bool(
        entry.get("active")
        or entry.get("isActive")
        or product.get("active")
        or product.get("isActive")
        or metadata.get("active")
    )
    is_inactive = _coerce_bool(
        entry.get("inactive")
        or entry.get("isInactive")
        or product.get("inactive")
        or product.get("isInactive")
        or metadata.get("inactive")
    )
    status_upper = str(status).upper() if status else ""
    if is_active is None and status_upper == "ACTIVE":
        is_active = True
    if is_inactive is None and status_upper == "INACTIVE":
        is_inactive = True
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
        "requestable": requestable,
        "is_active": is_active,
        "is_inactive": is_inactive,
        "status": status,
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

