import json
import re
import urllib.parse
from pathlib import Path
from typing import Callable, Optional
from models import ItemDict

BRAND_HINTS_FILE: Optional[Path] = None
_BRAND_HINTS_CACHE: list[dict] | None = None


def init_parser_paths(brand_hints_file: Path) -> None:
    """Configure where the parser reads/writes its brand database."""
    global BRAND_HINTS_FILE, _BRAND_HINTS_CACHE
    BRAND_HINTS_FILE = Path(brand_hints_file)
    _BRAND_HINTS_CACHE = None


def _maybe_log(logger: Optional[Callable[[str], None]], msg: str) -> None:
    if logger:
        try:
            logger(msg)
        except Exception:
            pass


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


def _ensure_brand_file(logger: Optional[Callable[[str], None]] = None) -> None:
    """Ensure the brand hints file exists so reads don't fail."""
    if BRAND_HINTS_FILE is None or BRAND_HINTS_FILE.exists():
        return
    try:
        BRAND_HINTS_FILE.write_text("[]", encoding="utf-8")
    except Exception:
        pass


def _load_brand_hints(logger: Optional[Callable[[str], None]] = None) -> list[dict]:
    global _BRAND_HINTS_CACHE
    if _BRAND_HINTS_CACHE is not None:
        return _BRAND_HINTS_CACHE
    hints: list[dict] = []
    try:
        _ensure_brand_file(logger=logger)
        if BRAND_HINTS_FILE and BRAND_HINTS_FILE.exists():
            text = BRAND_HINTS_FILE.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, list):
                hints = [entry for entry in data if isinstance(entry, dict)]
    except Exception:
        pass
    _BRAND_HINTS_CACHE = hints
    return hints


def _save_brand_hints(hints: list[dict]) -> None:
    global _BRAND_HINTS_CACHE
    try:
        if BRAND_HINTS_FILE is None:
            return
        BRAND_HINTS_FILE.write_text(json.dumps(hints, indent=2), encoding="utf-8")
        _BRAND_HINTS_CACHE = hints
    except Exception:
        pass


def _match_token(text: str, token: str) -> bool:
    pattern = rf"(?<![A-Z0-9]){re.escape(token.strip())}(?![A-Z0-9])"
    return re.search(pattern, text, flags=re.I) is not None


def _strip_trailing_code(value: str) -> str:
    parts = value.strip().split()
    if len(parts) >= 2 and re.fullmatch(r"[A-Z0-9]{1,3}", parts[-1]):
        parts = parts[:-1]
    return " ".join(parts).strip()


def _normalize_brand_key(value: str | None) -> str | None:
    if not value:
        return None
    stripped = _strip_trailing_code(str(value))
    cleaned = re.sub(r"[^A-Z0-9]", "", stripped.upper())
    return cleaned or None


def _heuristic_trim_brand(value: str) -> str:
    tokens = value.strip().split()
    kept = []
    for idx, tok in enumerate(tokens):
        clean_tok = re.sub(r"[^A-Za-z0-9-]", "", tok)
        if idx > 0 and (re.search(r"\d", clean_tok) or (clean_tok.isupper() and len(clean_tok) <= 4)):
            break
        kept.append(tok)
    if kept:
        return " ".join(kept).strip()
    return value.strip()


def canonical_brand(value: str | None) -> str | None:
    if not value:
        return None
    raw_upper = str(value).upper()
    if re.search(r"\bT2\.0\b|\bT2\b", raw_upper):
        return "Tyson 2.0"
    norm = _normalize_brand_key(value)
    for entry in _load_brand_hints():
        brand_name = entry.get("brand")
        display = entry.get("display") or brand_name
        if not brand_name:
            continue
        if norm and norm == _normalize_brand_key(brand_name):
            return display
        if norm and entry.get("display") and norm == _normalize_brand_key(entry.get("display")):
            return display
    return None


def format_brand(value: str | None) -> str | None:
    if not value:
        return None
    stripped = _strip_trailing_code(str(value))
    for entry in _load_brand_hints():
        brand_name = entry.get("brand")
        if not brand_name:
            continue
        tokens = entry.get("patterns") or entry.get("phrases") or []
        tokens = list(tokens) + [brand_name]
        for tok in tokens:
            if not tok:
                continue
            if stripped.upper().startswith(str(tok).upper()):
                display = entry.get("display") or brand_name
                return str(display)
    canonical = canonical_brand(stripped)
    if canonical:
        return canonical
    trimmed = _heuristic_trim_brand(stripped)
    return trimmed.title()


def infer_brand(producer: str | None, product_id: str | None, strain: str | None, source_text: str | None = None) -> str | None:
    combined = " ".join([p for p in (producer, product_id, strain, source_text) if p])
    if not combined:
        return None
    upper_text = f" {combined.upper()} "
    direct = canonical_brand(combined)
    if direct:
        return direct
    best_match = None
    for entry in _load_brand_hints():
        brand = entry.get("brand")
        tokens = entry.get("patterns") or entry.get("phrases") or []
        if brand:
            tokens = list(tokens) + [brand]
        if not brand or not isinstance(tokens, list):
            continue
        for tok in tokens:
            if not tok:
                continue
            tok_str = str(tok)
            if _match_token(upper_text, tok_str.upper()):
                score = len(tok_str)
                if not best_match or score > best_match[0] or (score == best_match[0] and len(str(brand)) > best_match[1]):
                    best_match = (score, len(str(brand)), entry)
    if best_match:
        entry = best_match[2]
        display = entry.get("display") or entry.get("brand")
        if display:
            return str(display)
    return None


def parse_clinic_text(text: str) -> list[ItemDict]:
    """Parse the copied Medicann page text into structured items."""
    items: list[dict] = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    def _normalize_header_line(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip().lower()

    pending_stock = None
    pending_strain_type = None
    pending_strain = None
    pending_strain_idx = None
    product_keywords = (
        "CANNABIS FLOWER",
        "CANNABIS OIL",
        "VAPE CARTRIDGE",
        "MEDICAL INHALATION DEVICE",
        "SUBLINGUAL OIL",
    )
    stock_keywords = ("IN STOCK", "LOW STOCK", "OUT OF STOCK", "NOT PRESCRIBABLE")
    i = 0
    while i < len(lines):
        line = lines[i]
        strain_line = None
        if not any(k in line.upper() for k in product_keywords):
            if re.match(r"^(Hybrid|Indica|Sativa)\b", line, re.I):
                strain_line = line
        if strain_line and ("|" in strain_line):
            left, right = [p.strip() for p in strain_line.split("|", 1)]
            pending_strain_type = left.title()
            pending_strain = right
            pending_strain_idx = i
            i += 1
            continue
        elif strain_line:
            pending_strain_type = strain_line.strip().title()
            pending_strain = None
            pending_strain_idx = i
            i += 1
            continue
        if (
            any(sk in line.upper() for sk in stock_keywords)
            and not any(k in line.upper() for k in product_keywords)
            and not re.match(r"^(Hybrid|Indica|Sativa)\b", line, re.I)
        ):
            if "|" not in line:
                pending_stock = line.strip()
                i += 1
                continue
        if any(k in line.upper() for k in product_keywords):
            m = re.match(r"^(?P<header>[^\(]+)\s*(?:\((?P<product_id>[^)]+)\))?\s*(?P<producer>.*)?$", line)
            header = m.group("header").strip() if m and m.group("header") else line
            product_id = (m.group("product_id").strip() if m and m.group("product_id") else None)
            producer = header
            is_smalls = bool(re.search(r"\b(SMALLS?|SMLS?|SML|SMALL BUDS?|BUDS?)\b", line, re.I))
            grams_hint = None
            if product_id:
                gm_pid = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\b", product_id, re.I)
                if gm_pid:
                    grams_hint = float(gm_pid.group(1))
            gm_head = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\b", line, re.I)
            if grams_hint is None and gm_head:
                grams_hint = float(gm_head.group(1))
            if product_id and re.search(r"\b(SMALLS?|SMLS?|SML|BUDS?)\b", product_id, re.I):
                product_id = None
            if product_id and re.search(r"\b(THC|CBD)\b", product_id, re.I):
                product_id = None
            ut = line.upper()
            if "OIL" in ut:
                product_type = "oil"
            elif "VAPE" in ut:
                product_type = "vape"
            elif "DEVICE" in ut:
                product_type = "device"
            else:
                product_type = "flower"
            strain = None
            strain_type = None
            if pending_strain_idx is not None and (i - pending_strain_idx) <= 2:
                if pending_strain_type and strain_type is None:
                    strain_type = pending_strain_type
                if pending_strain and strain is None:
                    strain = pending_strain

            stock = pending_stock
            next_pending_stock = None
            grams = ml = price = None
            if grams_hint is not None:
                grams = grams_hint
            thc = cbd = None
            thc_unit = cbd_unit = None
            stop_index = None
            smalls_flag = is_smalls
            last_index = i
            for j in range(i + 1, min(i + 12, len(lines))):
                last_index = j
                l = lines[j]
                if any(k in l.upper() for k in product_keywords):
                    if _normalize_header_line(l) == _normalize_header_line(line):
                        continue
                    stop_index = j - 1
                    break
                if (
                    any(sk in l.upper() for sk in stock_keywords)
                    and not re.match(r"^(Hybrid|Indica|Sativa)\b", l, re.I)
                ):
                    if "|" not in l:
                        next_pending_stock = l.strip()
                        stop_index = j
                        break
                if re.search(r"\b(SMALLS?|SMLS?|SML)\b", l, re.I):
                    smalls_flag = True
                if "|" in l and strain is None:
                    if re.search(r"\bTHC\b", l, re.I) and re.search(r"\bCBD\b", l, re.I):
                        pass
                    else:
                        left, right = [p.strip() for p in l.split("|", 1)]
                        if not re.search(r"\b(IN STOCK|LOW STOCK|OUT OF STOCK|NOT PRESCRIBABLE|FORMULATION ONLY)\b", left, re.I):
                            left_lower = left.lower()
                            right_lower = right.lower()
                            type_tokens = {"hybrid", "indica", "sativa"}
                            if left_lower in type_tokens:
                                strain_type = left.title()
                                strain = right
                            else:
                                strain = left
                                if "hybrid" in right_lower:
                                    strain_type = "Hybrid"
                                elif "indica" in right_lower:
                                    strain_type = "Indica"
                                elif "sativa" in right_lower:
                                    strain_type = "Sativa"
                                else:
                                    whole = l.lower()
                                    if "hybrid" in whole:
                                        strain_type = "Hybrid"
                                    elif "indica" in whole:
                                        strain_type = "Indica"
                                    elif "sativa" in whole:
                                        strain_type = "Sativa"
                                    else:
                                        strain_type = None
                elif strain_type is None and re.match(r"^(Hybrid|Indica|Sativa)\b", l, re.I):
                    strain_type = l.strip().title()
                num = r"(\d+(?:\.\d+)?|\.\d+)"
                gm = re.search(rf"{num}\s*(?:g|grams?)\b", l, re.I)
                if gm is None:
                    gm = re.search(rf"{num}\s*(?:g|grams?)\b", line, re.I)
                if gm is None:
                    gm = re.search(rf"{num}\s*(?:g|grams?)\b", header, re.I)
                if gm is None:
                    gm = re.search(rf"{num}\s*(?:g|grams?)\b", product_id or "", re.I)
                if gm is None:
                    gm = re.search(rf"\bT\s*{num}\b", line, re.I)
                if gm is None:
                    gm = re.search(rf"\bT\s*{num}\b", header, re.I)
                if gm is None:
                    gm = re.search(rf"\bT\s*{num}\b", product_id or "", re.I)
                mlm = re.search(rf"{num}\s*(?:ml|mL)\b", l, re.I)
                if gm and grams is None:
                    try:
                        grams = float(gm.group(1))
                    except Exception:
                        grams = None
                if mlm and ml is None:
                    try:
                        ml = float(mlm.group(1))
                    except Exception:
                        ml = None
                pm = re.search(r"(\d+(?:[.,]\d+)?)", l)
                if pm and price is None:
                    has_currency = bool(re.search(r"[£$€Ł]|GBP|USD|EUR|PLN|ZŁ|ZL", l, re.I)) or ("ś" in l)
                    has_decimal = bool(re.search(r"\d+[.,]\d{2}", l))
                    if has_currency or (has_decimal and len(l.strip()) <= 12):
                        try:
                            price = float(pm.group(1).replace(",", "."))
                        except Exception:
                            price = None
                        if price is not None:
                            stop_index = j
                            break
                tm = re.search(rf"THC\s*<?\s*{num}\s*([a-z/%]+)?", l, re.I)
                if tm and thc is None:
                    try:
                        thc = float(tm.group(1))
                    except Exception:
                        thc = None
                    u = (tm.group(2) or "").strip().lower().replace(" ", "")
                    if not u and "%" in l[tm.start(): tm.end() + 8]:
                        u = "%"
                    if "mg/ml" in u or "/ml" in u:
                        thc_unit = "mg/ml"
                    elif "mg/g" in u or "/g" in u:
                        thc_unit = "mg/g"
                    elif "%" in u:
                        thc_unit = "%"
                    else:
                        thc_unit = u or None
                cm = re.search(rf"CBD\s*<?\s*{num}\s*([a-z/%]+)?", l, re.I)
                if cm and cbd is None:
                    try:
                        cbd = float(cm.group(1))
                    except Exception:
                        cbd = None
                    u2 = (cm.group(2) or "").strip().lower().replace(" ", "")
                    if not u2 and "%" in l[cm.start(): cm.end() + 8]:
                        u2 = "%"
                    if "mg/ml" in u2 or "/ml" in u2:
                        cbd_unit = "mg/ml"
                    elif "mg/g" in u2 or "/g" in u2:
                        cbd_unit = "mg/g"
                    elif "%" in u2:
                        cbd_unit = "%"
                    else:
                        cbd_unit = u2 or None
            if strain_type is None and product_type == "flower":
                hay = " ".join([str(v) for v in (strain, header, product_id, line) if v])
                if re.search(r"\bhybrid\b", hay, re.I):
                    strain_type = "Hybrid"
                elif re.search(r"\bindica\b", hay, re.I):
                    strain_type = "Indica"
                elif re.search(r"\bsativa\b", hay, re.I):
                    strain_type = "Sativa"
            if grams is None and product_type == "flower":
                grams = 10.0
            items.append(
                {
                    "product_id": product_id,
                    "producer": producer,
                    "brand": None,
                    "strain": strain,
                    "strain_type": strain_type,
                    "stock": stock,
                    "product_type": product_type,
                    "is_smalls": smalls_flag,
                    "grams": grams,
                    "ml": ml,
                    "price": price,
                    "thc": thc,
                    "thc_unit": thc_unit,
                    "cbd": cbd,
                    "cbd_unit": cbd_unit,
                }
            )
            if stop_index is not None:
                i = stop_index
            else:
                i = max(i, last_index)
            pending_stock = next_pending_stock
            pending_strain_type = None
            pending_strain = None
            pending_strain_idx = None

            def _clean_name(s):
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
                out = re.sub(r"\bBUDS?\b", "", out, flags=re.I)
                out = re.sub(r"\bT\d+(?::C?\d+)?\b", "", out, flags=re.I)
                out = re.sub(r"THC[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
                out = re.sub(r"CBD[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
                out = re.sub(r"[\s\\-_/]+", " ", out).strip()
                return out

            raw_producer = items[-1].get("producer")
            raw_strain = items[-1].get("strain")
            raw_product_id = items[-1].get("product_id")
            items[-1]["producer"] = _clean_name(raw_producer)
            items[-1]["strain"] = _clean_name(raw_strain)
            cleaned_pid = _clean_name(raw_product_id)
            if cleaned_pid and re.search(r"\b(SMALLS?|SMLS?|SML|BUDS?)\b", cleaned_pid, re.I):
                cleaned_pid = None
            items[-1]["product_id"] = cleaned_pid or None
            inferred = infer_brand(raw_producer, raw_product_id, raw_strain, line)
            items[-1]["brand"] = format_brand(inferred or items[-1].get("brand"))
        i += 1
    return items


def seed_brand_db_if_needed(target_file: Path, bundled_copy: Path, logger: Optional[Callable[[str], None]] = None) -> None:
    """On first run, seed the parser database from the bundled copy if none exists."""
    try:
        if target_file.exists():
            return
        if bundled_copy.exists():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(bundled_copy.read_text(encoding="utf-8"), encoding="utf-8")
            _maybe_log(logger, f"Seeded parser database from bundled copy to {target_file}")
    except Exception as exc:
        _maybe_log(logger, f"Failed to seed parser database: {exc}")
