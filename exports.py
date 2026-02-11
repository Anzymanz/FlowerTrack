from __future__ import annotations

import base64
import html
import json
import math
import os
import re
import time
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from export_template import HTML_TEMPLATE
from logger import log_event

try:
    from parser import get_google_medicann_link, make_identity_key as _parser_identity_key  # type: ignore
except Exception:

    def get_google_medicann_link(producer, strain):
        q = " ".join([p for p in (producer or '', strain or '') if p]).strip()
        return "https://www.google.com/search?q=" + urllib.parse.quote(q + " medbud.wiki")

    def _parser_identity_key(item: dict) -> str:
        # Fallback for environments where parser import fails (standalone export usage).
        return ""

_ASSET_CACHE: dict[str, str] | None = None
_ASSETS_DIR: Optional[Path] = None
_EXPORTS_DIR: Optional[Path] = None
EXPORT_WARN_MB = 10.0


def _ensure_assets_dir(default: Optional[Path] = None) -> None:
    """Ensure assets dir is set; fallback to provided default or ./assets next to this file."""
    global _ASSETS_DIR, _ASSET_CACHE
    if _ASSETS_DIR is None:
        candidate = default or (Path(__file__).resolve().parent / "assets")
        if candidate.exists():
            _ASSETS_DIR = candidate
            if _ASSET_CACHE is None:
                _ASSET_CACHE = {}
def _load_asset(name: str) -> str | None:
    """Return data URI for a given asset name (filename)."""
    global _ASSET_CACHE
    if _ASSET_CACHE is None:
        _ASSET_CACHE = {}
    if name in _ASSET_CACHE:
        return _ASSET_CACHE[name]
    if _ASSETS_DIR is None:
        return None
    img_path = _ASSETS_DIR / name
    try:
        raw = img_path.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        uri = f"data:image/png;base64,{encoded}"
        _ASSET_CACHE[name] = uri
        return uri
    except Exception:
        return None


def _normalize_val(val):
    if val is None:
        return ""
    if isinstance(val, float):
        try:
            return f"{val:.4f}"
        except Exception:
            return str(val)
    return str(val).strip().lower()


def make_identity_key(item: dict) -> str:
    if _parser_identity_key is not None:
        try:
            key = _parser_identity_key(item)
            if key:
                return key
        except Exception:
            pass
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


def format_brand(value: str | None) -> str:
    """Simple brand formatter for exports."""
    if not value:
        return ""
    parts = []
    for tok in str(value).split():
        parts.append(tok if tok.isupper() else tok.title())
    return " ".join(parts)


def _country_code2(code: str | None) -> str | None:
    if not code:
        return None
    raw = str(code).strip().upper()
    alpha3_to_alpha2 = {
        "CAN": "CA",
        "USA": "US",
        "US": "US",
        "GBR": "GB",
        "UK": "GB",
        "DEU": "DE",
        "DE": "DE",
        "NLD": "NL",
        "NL": "NL",
        "AUS": "AU",
        "AU": "AU",
        "NZL": "NZ",
        "NZ": "NZ",
        "ESP": "ES",
        "ES": "ES",
        "PRT": "PT",
        "PT": "PT",
        "ITA": "IT",
        "IT": "IT",
        "ISR": "IL",
        "IL": "IL",
        "CHE": "CH",
        "CH": "CH",
        "DNK": "DK",
        "DK": "DK",
        "NOR": "NO",
        "NO": "NO",
        "SWE": "SE",
        "SE": "SE",
        "POL": "PL",
        "PL": "PL",
    }
    code2 = alpha3_to_alpha2.get(raw, raw)
    if len(code2) != 2 or not code2.isalpha():
        return None
    return code2.lower()


def _flag_cdn_url(code: str | None) -> str | None:
    code2 = _country_code2(code)
    if not code2:
        return None
    return f"https://flagcdn.com/24x18/{code2}.png"


def init_exports(assets_dir: Path, exports_dir: Optional[Path] = None) -> None:
    global _ASSETS_DIR, _EXPORTS_DIR, _ASSET_CACHE
    _ASSETS_DIR = assets_dir
    _EXPORTS_DIR = Path(exports_dir) if exports_dir else (assets_dir.parent / "Exports")
    _ASSET_CACHE = {}

def set_exports_dir(exports_dir: Path) -> None:
    global _EXPORTS_DIR
    _EXPORTS_DIR = exports_dir


def export_size_warning(path: Path, warn_mb: float = EXPORT_WARN_MB) -> str | None:
    try:
        size_bytes = path.stat().st_size
    except Exception:
        return None
    size_mb = size_bytes / (1024 * 1024)
    if size_mb >= warn_mb:
        return f"Export HTML is {size_mb:.1f} MB; large exports may be slow to open."
    return None


def build_launch_url(producer: str | None, strain: str | None) -> str:
    """Reusable launcher URL for search links."""
    return get_google_medicann_link(producer or '', strain)

def _render_card_html(
    *,
    it: dict,
    card_classes: str,
    price_border_class: str,
    data_price_attr: str,
    data_thc_attr: str,
    data_cbd_attr: str,
    brand: str,
    stock_text: str,
    card_key: str,
    fav_key: str,
    is_out: bool,
    image_html: str,
    type_icon_dark: str | None,
    type_icon_light: str | None,
    strain_badge_src: str | None,
    price_badge: str,
    heading_html: str,
    product_type_label: str,
    qty_pill_text: str,
    price_pill: str,
    stock_pill: str,
    ppg: float | None,
    ppc: float | None,
    disp_thc: str,
    disp_cbd: str,
) -> str:
    return f"""
    <div class='{card_classes}{price_border_class}' style='position:relative;'
          data-price='{esc_attr(data_price_attr)}'
      data-thc='{esc_attr(data_thc_attr)}'
      data-cbd='{esc_attr(data_cbd_attr)}'
      data-pt='{esc_attr((it.get('product_type') or '').lower())}'
      data-strain-type='{esc_attr(it.get('strain_type') or '')}'
      data-strain='{esc_attr(it.get("strain") or '')}'
      data-brand='{esc_attr(brand or '')}'
      data-producer='{esc_attr(it.get('producer') or '')}'
      data-product-id='{esc_attr(it.get("product_id") or '')}'
      data-stock='{esc_attr(stock_text)}'
      data-stock-status='{esc_attr((it.get("stock_status") or it.get("stock") or "").upper())}'
      data-requestable='{1 if it.get("requestable") else 0}'
      data-active='{1 if it.get("is_active") else 0}'
      data-inactive='{1 if it.get("is_inactive") else 0}'
      data-status='{esc_attr(it.get("status") or '')}'
      data-irradiation='{esc_attr(it.get("irradiation_type") or '')}'
      data-key='{esc_attr(card_key)}'
      data-favkey='{esc_attr(fav_key)}'
      data-smalls='{1 if it.get("is_smalls") else 0}'
      data-removed='{1 if it.get("is_removed") else 0}'
      data-out='{1 if is_out else 0}'>
    <button class='fav-btn' onclick='toggleFavorite(this)' title='Favorite this item'>★</button>
    {image_html if image_html else ("<img class='type-badge' data-theme-icon='dark' loading='lazy' decoding='async' src='" + esc_attr(type_icon_dark) + "' alt='" + esc_attr(it.get('product_type') or '') + "' />") if type_icon_dark else ""}
    {"" if image_html else ("<img class='type-badge' data-theme-icon='light' loading='lazy' decoding='async' src='" + esc_attr(type_icon_light) + "' alt='" + esc_attr(it.get('product_type') or '') + "' style='display:none;' />") if type_icon_light else ""}
    {"" if image_html else (("<img class='strain-badge' loading='lazy' decoding='async' src='" + esc_attr(strain_badge_src) + "' alt='" + esc_attr(it.get('strain_type') or '') + "' />") if strain_badge_src else "")}
    <div style='display:flex;flex-direction:column;align-items:flex-start;gap:4px;'>
      {price_badge}
      <h3 class='card-title'>{heading_html}</h3>
    </div>
<a class='search' style='position:absolute;bottom:12px;right:44px;font-size:18px;padding:6px 8px;border-radius:6px;min-width:auto;width:28px;height:28px;display:flex;align-items:center;justify-content:center;border:none' href='{esc_attr(build_launch_url(it.get('producer'), it.get('strain')))}' target='_blank' title='Search Medbud.wiki'>🔎</a>
      <p class="brand-line"><strong>{esc(brand)}</strong></p>
        <p class='small'>
        {esc(product_type_label)}
        </p>
  <div class='card-content'>
    <div>
      {price_pill}
      <span class='pill'>{esc(qty_pill_text or '⚖️ ?')}</span>
      {stock_pill}
        {f"<span class='pill'>£/g {ppg:.2f}</span>" if ppg is not None else ''}
        {f"<span class='pill'>£/pc {ppc:.2f}</span>" if ppc is not None else ''}
        {f"<span class='pill'>🍃 {esc(it.get('strain_type'))}</span>" if it.get('strain_type') else ''}
        {f"<span class='pill pill-flag'><img class='flag-icon' loading='lazy' decoding='async' src='{esc_attr(_flag_cdn_url(it.get('origin_country')))}' alt='{esc_attr(it.get('origin_country') or '')}' /> {esc(it.get('origin_country'))}</span>" if _flag_cdn_url(it.get('origin_country')) else ''}
        {f"<span class='pill'>☢️ {esc(it.get('irradiation_type'))}</span>" if (it.get('irradiation_type') and (it.get('product_type') or '').lower() == 'flower') else ''}
    </div>
    <div class='small'>🌞THC: {esc(disp_thc)}</div>
    <div class='small'>🌙CBD: {esc(disp_cbd)}</div>
    <div class='card-actions'>
      <button class='btn-basket' onclick='toggleBasketItem(this)' onmouseenter='basketHover(this,true)' onmouseleave='basketHover(this,false)'>Add to basket</button>
    </div>
  </div>
 </div>
"""


# ---------------- EXPORT HTML ----------------


def esc(value):
    return html.escape("" if value is None else str(value))


def esc_attr(value):
    return html.escape("" if value is None else str(value), quote=True)


def export_html(data, path, fetch_images=False):
    _ensure_assets_dir()
    out_path = Path(path)
    cards: list[str] = []

    def get_badge_src(strain_type: str | None, product_type: str | None) -> str | None:
        """Return a data URI for the strain badge image if available."""
        if not strain_type:
            return None
        if product_type and product_type.lower() in {"vape", "oil", "device", "pastille"}:
            return None
        return _load_asset(f"{strain_type.title()}.png")

    def get_type_icon(pt: str | None, theme: str) -> str | None:
        """Return a data URI for product-type icon respecting theme (dark/light)."""
        if not pt:
            return None
        if pt.lower() == "vape":
            return _load_asset("VapeLight.png" if theme == "light" else "VapeDark.png")
        if pt.lower() == "oil":
            return _load_asset("OilLight.png" if theme == "light" else "OilDark.png")
        return None

    def display_product_type(pt: str | None) -> str:
        norm = str(pt or "").strip().lower()
        if norm == "pastille":
            return "Pastilles"
        return str(pt or "").title()

    def normalize_pct(value, unit):
        if value is None:
            return None
        if not unit:
            return value
        u = unit.lower()
        try:
            if "mg" in u:
                return float(value) / 10.0
            if "%" in u:
                return float(value)
        except Exception:
            return None
        return float(value)

    def norm(s: str | None) -> str:
        if not s:
            return ""
        return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")

    # Pre-compute slider bounds
    price_values = [float(it.get("price")) for it in data if isinstance(it.get("price"), (int, float))]
    price_min_bound = math.floor(min(price_values)) if price_values else 0
    price_max_bound = math.ceil(max(price_values)) if price_values else 0
    thc_values: list[float] = []
    for it in data:
        val = normalize_pct(it.get("thc"), it.get("thc_unit"))
        if isinstance(val, (int, float)):
            if (it.get('product_type') or '').lower() == "flower":
                thc_values.append(float(val))
    if not thc_values:
        for it in data:
            val = normalize_pct(it.get("thc"), it.get("thc_unit"))
            if isinstance(val, (int, float)):
                thc_values.append(float(val))
    thc_min_bound = math.floor(min(thc_values)) if thc_values else 0
    thc_max_bound = math.ceil(max(thc_values)) if thc_values else 0
    if thc_max_bound < 40:
        thc_max_bound = 40
    elif thc_max_bound > 60:
        thc_max_bound = 60
    if thc_min_bound > thc_max_bound:
        thc_min_bound = thc_max_bound

    def fav_key_for(item: dict) -> str:
        brand_norm = norm(format_brand(item.get("brand") or item.get("producer") or ''))
        strain_norm = norm(item.get("strain") or '')
        if brand_norm or strain_norm:
            combo = f"{brand_norm}-{strain_norm}".strip("-")
        else:
            prod_norm = norm(item.get("producer"))
            pid_norm = norm(item.get("product_id"))
            combo = f"{prod_norm}-{pid_norm}".strip("-")
        if not combo:
            combo = f"item-{abs(hash(str(item)))%10_000_000}"
        return combo

    for it in data:
        price = it.get("price")
        if it.get("is_removed") and not isinstance(price, (int, float)):
            price = 0
        grams = it.get("grams")
        ppg = (price / grams) if isinstance(price, (int, float)) and isinstance(grams, (int, float)) and grams else None
        ppc = None
        if (it.get("product_type") or "").lower() == "pastille":
            explicit_ppc = it.get("price_per_unit")
            if isinstance(explicit_ppc, (int, float)):
                ppc = float(explicit_ppc)
            else:
                unit_count = it.get("unit_count")
                if isinstance(price, (int, float)) and isinstance(unit_count, (int, float)) and unit_count:
                    ppc = float(price) / float(unit_count)
        qty_pill_text = "⚖️ ?"
        product_type = str(it.get("product_type") or "").strip().lower()
        if product_type == "pastille":
            count = it.get("unit_count")
            if count is None and it.get("grams") is not None:
                # Backward compatibility for older parses where unit count landed in grams.
                count = it.get("grams")
            if isinstance(count, (int, float)):
                if float(count).is_integer():
                    count_str = str(int(float(count)))
                else:
                    count_str = f"{float(count):g}"
            elif count is not None:
                count_str = str(count)
            else:
                count_str = "?"
            qty_pill_text = f"🍬 {count_str}"
        elif it.get("grams") is not None:
            qty_pill_text = f"⚖️ {it['grams']}g"
        elif it.get("ml") is not None:
            qty_pill_text = f"⚖️ {it['ml']}ml"

        type_icon_dark = get_type_icon(it.get('product_type'), "dark")
        image_url = (it.get("brand_logo_url") or it.get("image_url") or '').strip()
        image_html = ""
        if image_url:
            alt_text = it.get("brand") or it.get("producer") or it.get("title") or ""
            image_html = (
                "<img class='type-badge' loading='lazy' decoding='async' src='"
                + esc_attr(image_url)
                + "' alt='"
                + esc_attr(alt_text)
                + "' data-fullsrc='"
                + esc_attr(image_url)
                + "' onclick='openImageModal(this.dataset.fullsrc, this.alt)' />"
            )
        type_icon_light = get_type_icon(it.get('product_type'), "light")
        strain_badge_src = get_badge_src(it.get('strain_type'), it.get('product_type'))
        has_type_icon = bool(image_html or type_icon_dark or type_icon_light)

        thc_raw = it.get("thc")
        thc_unit = it.get("thc_unit")
        cbd_raw = it.get("cbd")
        cbd_unit = it.get("cbd_unit")
        thc_pct = normalize_pct(thc_raw, thc_unit)
        cbd_pct = normalize_pct(cbd_raw, cbd_unit)

        def clean_name(s):
            if not s:
                return s
            out = str(s)
            out = re.sub(
                r"\b(IN STOCK|LOW STOCK|OUT OF STOCK|NOT PRESCRIBABLE|NOT PRESCRIBABLE DO NOT SELECT|FORMULATION ONLY|FULL SPECTRUM)\b",
                "",
                out,
                flags=re.I,
            )
            out = re.sub(r"\b(SMALLS?|SMLS?|SML)\b", "", out, flags=re.I)
            out = re.sub(r"\bT\d+(?::C?\d+)?\b", "", out, flags=re.I)
            out = re.sub(r"THC[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
            out = re.sub(r"CBD[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
            out = re.sub(r"\s*\([^)]*(THC|CBD|%)[^)]*\)\s*$", "", out, flags=re.I)
            out = re.sub(r"\s*\([^)]*$", "", out)
            out = re.sub(r"\s*[\(\[\{]+$", "", out)
            out = re.sub(r"[\s\-_/]+", " ", out).strip()
            return out

        strain_name = clean_name(it.get("strain") or '')
        if it.get('brand'):
            b = format_brand(it.get('brand'))
            if b and strain_name:
                pat = re.compile(re.escape(str(b)), re.I)
                strain_name = pat.sub("", strain_name).strip()
                first_tok = b.split()[0]
                strain_name = re.sub(rf"\b{re.escape(first_tok)}\b", "", strain_name, flags=re.I).strip()
                strain_name = re.sub(r"\s{2,}", " ", strain_name).strip()
        heading = strain_name or clean_name(it.get('title') or it.get('producer') or it.get('product_type') or "-")
        if it.get("is_smalls") and heading:
            heading = f"{heading} (Smalls)"
        brand = format_brand(it.get('brand') or it.get('producer') or '')

        def display_strength(raw, unit, pct):
            if raw is None:
                return "?"
            base = f"{raw} {unit or ''}".strip()
            if pct is not None and (unit and "%" not in unit):
                return f"{base} ({pct:.1f}%)"
            return base

        disp_thc = display_strength(thc_raw, thc_unit, thc_pct)
        disp_cbd = display_strength(cbd_raw, cbd_unit, cbd_pct)
        data_price_attr = "" if price is None else str(price)
        data_thc_attr = "" if thc_pct is None else f"{thc_pct}"
        data_cbd_attr = "" if cbd_pct is None else f"{cbd_pct}"
        card_key = make_identity_key(it)
        fav_key = fav_key_for(it)
        price_delta = it.get("price_delta")
        price_class = "pill"
        delta_text = ""
        if isinstance(price_delta, (int, float)) and price is not None:
            if price_delta > 0:
                price_class += " price-up"
                delta_text = f" (+£{abs(price_delta):.2f})"
            elif price_delta < 0:
                price_class += " price-down"
                delta_text = f" (-£{abs(price_delta):.2f})"
        price_label = "??" if price is None else f"£{price:.2f}"
        price_pill = f"<span class='{price_class}' data-pricedelta='{esc_attr(price_delta if price_delta is not None else '')}'>💵 {esc(price_label + delta_text)}</span>"
        price_badge = ""
        price_border_class = ""
        if isinstance(price_delta, (int, float)) and price_delta:
            badge_cls = "badge-price-up" if price_delta > 0 else "badge-price-down"
            badge_text = f"New price {'+' if price_delta>0 else '-'}£{abs(price_delta):.2f}"
            price_badge = f"<span class='{badge_cls}'>{esc(badge_text)}</span>"
            price_border_class = " card-price-up" if price_delta > 0 else " card-price-down"
        stock_text = (it.get("stock_detail") or it.get("stock_status") or it.get("stock") or '').strip()
        stock_upper = (it.get("stock_status") or it.get("stock") or '').upper()
        is_out = ("OUT" in stock_upper) or (it.get("stock_remaining") == 0)
        if it.get("stock_remaining") is not None:
            remaining_val = it.get("stock_remaining")
            if isinstance(remaining_val, (int, float)) and remaining_val >= 15:
                stock_text = "15+ remaining"
            else:
                stock_text = f"{remaining_val} remaining"
        stock_delta = it.get('stock_delta')
        stock_pill_class = 'pill'
        if isinstance(stock_delta, (int, float)) and stock_delta:
            stock_pill_class += ' stock-up' if stock_delta > 0 else ' stock-down'
        elif it.get("stock_changed"):
            stock_pill_class += ' stock-change'
        stock_pill = f"<span class='{stock_pill_class}'>📊 {esc(stock_text)}</span>" if stock_text else ""
        stock_indicator = (
            f"<span class='stock-indicator "
            f"{('stock-not-prescribable' if ((it.get('stock_status') or it.get('stock')) and 'NOT' in ((it.get('stock_status') or it.get('stock') or '').upper())) else ('stock-in' if ((it.get('stock_status') or it.get('stock')) and 'IN STOCK' in ((it.get('stock_status') or it.get('stock') or '').upper())) else ('stock-low' if ((it.get('stock_status') or it.get('stock')) and 'LOW' in ((it.get('stock_status') or it.get('stock') or '').upper())) else ('stock-out' if ((it.get('stock_status') or it.get('stock')) and 'OUT' in ((it.get('stock_status') or it.get('stock') or '').upper())) else ''))))}"
            f"' title='{esc(it.get('stock_detail') or it.get('stock') or '')}'></span>"
        )
        heading_html = f"{stock_indicator}{esc(heading)}"
        card_classes = "card"
        if is_out:
            card_classes += " card-out"
        if has_type_icon:
            card_classes += " has-type-icon"
        cards.append(
            _render_card_html(
                it=it,
                card_classes=card_classes,
                price_border_class=price_border_class,
                data_price_attr=data_price_attr,
                data_thc_attr=data_thc_attr,
                data_cbd_attr=data_cbd_attr,
                brand=brand,
                stock_text=stock_text,
                card_key=card_key,
                fav_key=fav_key,
                is_out=is_out,
                image_html=image_html,
                type_icon_dark=type_icon_dark,
                type_icon_light=type_icon_light,
                strain_badge_src=strain_badge_src,
                price_badge=price_badge,
                heading_html=heading_html,
                product_type_label=display_product_type(it.get("product_type")),
                qty_pill_text=qty_pill_text,
                price_pill=price_pill,
                stock_pill=stock_pill,
                ppg=ppg,
                ppc=ppc,
                disp_thc=disp_thc,
                disp_cbd=disp_cbd,
            )
        )
    cards_html = "".join(cards)
    html_text = HTML_TEMPLATE.replace("__CARDS__", cards_html)
    history_path = None
    try:
        appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
        history_path = appdata / "FlowerTrack" / "logs" / "changes.ndjson"
    except Exception:
        history_path = None
    history_entries: list[dict] = []
    if history_path and history_path.exists():
        try:
            lines = history_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-50:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if isinstance(entry, dict):
                        trimmed = dict(entry)
                        for key in (
                            "new_items",
                            "removed_items",
                            "price_changes",
                            "stock_changes",
                            "out_of_stock_changes",
                            "restock_changes",
                        ):
                            items = trimmed.get(key)
                            if isinstance(items, list) and len(items) > 50:
                                trimmed[key] = items[:50]
                        history_entries.append(trimmed)
                except Exception:
                    history_entries.append({"_raw": line})
        except Exception:
            history_entries = []
    history_json = "[]"
    history_b64 = ""
    try:
        history_json = json.dumps(history_entries, ensure_ascii=False)
        history_b64 = base64.b64encode(history_json.encode("utf-8")).decode("ascii")
    except Exception:
        history_json = "[]"
        history_b64 = ""
    # Avoid closing the script tag when embedding raw JSON.
    history_json_safe = history_json.replace("</", "<\\/")
    html_text = html_text.replace("__CHANGES_JSON_B64__", history_b64)
    html_text = html_text.replace("__CHANGES_JSON__", history_json_safe)
    try:
        history_file = out_path.with_name("changes_latest.json")
        history_file.write_text(history_json, encoding="utf-8")
    except Exception:
        pass
    in_stock = 0
    low_stock = 0
    out_stock = 0
    type_counts = {"flower": 0, "oil": 0, "vape": 0, "pastille": 0}
    for it in data:
        if it.get("is_removed"):
            continue
        pt = str(it.get("product_type") or "").strip().lower()
        if pt in type_counts:
            type_counts[pt] += 1
        remaining = it.get("stock_remaining")
        status = (it.get("stock_status") or it.get("stock") or "").upper()
        if isinstance(remaining, (int, float)):
            if remaining <= 0:
                out_stock += 1
            elif remaining < 15:
                low_stock += 1
            else:
                in_stock += 1
            continue
        if "OUT" in status:
            out_stock += 1
        elif "LOW" in status:
            low_stock += 1
        elif "IN STOCK" in status:
            in_stock += 1
        else:
            in_stock += 1
    total_products = in_stock + low_stock + out_stock
    exported_at = datetime.now()
    exported_ms = int(time.time() * 1000)
    html_text = html_text.replace(
        "<body>",
        (
            f"<body data-exported='{esc_attr(exported_at.strftime('%Y-%m-%d %H:%M:%S'))}' "
            f"data-exported-ms='{exported_ms}' data-count='{total_products}' "
            f"data-in-stock='{in_stock}' data-low-stock='{low_stock}' "
            f"data-out-stock='{out_stock}' data-flower-count='{type_counts['flower']}' "
            f"data-oil-count='{type_counts['oil']}' data-vape-count='{type_counts['vape']}' "
            f"data-pastille-count='{type_counts['pastille']}'>"
        ),
    )
    html_text = html_text.replace("{price_min_bound}", str(price_min_bound))
    html_text = html_text.replace("{price_max_bound}", str(price_max_bound))
    html_text = html_text.replace("{thc_min_bound}", str(thc_min_bound))
    html_text = html_text.replace("{thc_max_bound}", str(thc_max_bound))
    out_path.write_text(html_text, encoding="utf-8")
    try:
        from export_server import notify_export_updated
        notify_export_updated(str(exported_ms))
    except Exception:
        pass
    
def export_html_auto(
    data, exports_dir: Optional[Path] = None, open_file: bool = False, fetch_images=False, max_files: int = 1
):

    _ensure_assets_dir()
    d = Path(exports_dir or _EXPORTS_DIR or ".")
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone().strftime('%Y-%m-%d_%H-%M-%S%z')
    fname = f"export-{ts}.html"
    path = d / fname
    export_html(data, path, fetch_images=fetch_images)
    cleanup_html_exports(d, max_files=max_files)
    if open_file:
        try:
            if os.name == 'nt':
                os.startfile(path)
            else:
                webbrowser.open(path.as_uri())
        except Exception:
            pass
    return path


def cleanup_html_exports(exports_dir: Optional[Path] = None, max_files: int = 20) -> None:
    """Keep only the newest `max_files` HTML exports."""
    try:
        d = Path(exports_dir or _EXPORTS_DIR or ".")
        files = sorted(d.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[max_files:]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception as exc:
        log_event("exports.cleanup_failed", {"error": str(exc)})
