import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.utils.normalize import (
    BOROUGH_CODE_TO_NAME,
    normalize_address,
    normalize_bbl,
    normalize_borough,
)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().split())


def normalize_street(value: str | None) -> str:
    text = normalize_text(value)
    return text.replace(".", "").upper()

ALIASES: Dict[str, List[str]] = {
    "bbl": ["bbl"],
    "borough": ["borough", "boro", "brgh"],
    "houseno": ["houseno", "housenum", "house_no", "house"],
    "street": ["street", "stname", "streetname", "st", "sname"],
    "zipcode": ["zipcode", "zip", "zip_code"],
    "address": ["address", "addr"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng"],
}


def _split_address(address: Any) -> tuple[Optional[str], Optional[str]]:
    if address in (None, ""):
        return None, None
    text = str(address).strip()
    if not text:
        return None, None
    parts = text.split(" ", 1)
    if len(parts) == 1:
        return None, text
    houseno, remainder = parts[0], parts[1]
    if houseno.isdigit():
        return houseno, remainder
    return None, text


def normalize_pluto_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    canonical = { (k or "").strip().lower(): v for k, v in raw.items() }

    houseno = canonical.get("houseno") or canonical.get("housenum") or canonical.get("house")
    street = canonical.get("street") or canonical.get("stname")
    if not houseno or not street:
        addr_h, addr_s = _split_address(canonical.get("address"))
        houseno = houseno or addr_h
        street = street or addr_s

    addr = normalize_address(houseno, street)
    houseno_clean = addr.house_number
    street_clean = addr.street
    borough_code, borough_name = normalize_borough(canonical.get("borough"))
    if not borough_name:
        bbl_guess = normalize_text(canonical.get("bbl"))
        if bbl_guess:
            borough_name = BOROUGH_CODE_TO_NAME.get(bbl_guess[:1], borough_name)
    zipcode_clean = normalize_text(canonical.get("zipcode")) or None

    latitude = to_float(canonical.get("latitude"))
    longitude = to_float(canonical.get("longitude"))

    return {
        "bbl": normalize_text(canonical.get("bbl")).upper() or None,
        "borough": borough_code,
        "borough_name": borough_name,
        "houseno": houseno_clean,
        "street": street_clean,
        "zipcode": zipcode_clean,
        "latitude": latitude,
        "longitude": longitude,
        "address": canonical.get("address"),
        "__raw__": raw,
    }


def canonicalize_headers(headers: List[str]) -> Tuple[Dict[int, str], List[str]]:
    alias_lookup: Dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        alias_lookup[_canon_header(canonical)] = canonical
        for alias in aliases:
            alias_lookup[_canon_header(alias)] = canonical

    mapping: Dict[int, str] = {}
    canonical_headers: List[str] = []
    for idx, header in enumerate(headers):
        token = _canon_header(header)
        canonical = alias_lookup.get(token, token)
        mapping[idx] = canonical
        canonical_headers.append(canonical)
    return mapping, canonical_headers


def derive_houseno_street(address: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if address in (None, ""):
        return None, None
    text = address.strip()
    if not text:
        return None, None
    parts = text.split(" ", 1)
    if len(parts) == 1:
        return None, text
    houseno, remainder = parts[0], parts[1]
    if houseno.replace("-", "").isdigit():
        return houseno, remainder
    return None, text


def to_borough(value: Optional[str]) -> Optional[str]:
    _, borough_name = normalize_borough(value)
    return borough_name


def to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_dob_permit(row: Dict[str, Any]) -> Dict[str, Any]:
    job_number = _first_nonempty(
        row,
        (
            "job_number",
            "job__",
            "job",
            "job#",
        ),
    )
    if not job_number:
        return {}

    filing_date = _parse_date(
        row.get("filing_date")
        or row.get("filed_date")
        or row.get("date")
    )
    latest_status_date = _parse_date(
        row.get("latest_status_date")
        or row.get("issuance_date")
    )

    borough_value = _first_nonempty(
        row,
        ("borough", "borocode", "boro", "borocode1"),
    )
    borough_code, borough_name = normalize_borough(borough_value)
    block_value = _first_nonempty(row, ("block", "block__", "block_num"))
    lot_value = _first_nonempty(row, ("lot", "lot__", "lot_num"))
    bbl = normalize_bbl(borough_code or borough_value, block_value, lot_value)
    if not bbl:
        bbl = _clean_string(row.get("bbl")) or None

    addr = normalize_address(
        _first_nonempty(row, ("house__", "house__no", "house_no", "house_number")),
        _first_nonempty(row, ("street_name", "streetname", "street")),
    )

    normalized = {
        "job_number": job_number,
        "bbl": bbl,
        "house_no": addr.house_number,
        "street_name": addr.street,
        "borough": borough_name or _clean_string(row.get("borough")),
        "job_type": _clean_string(row.get("job_type")),
        "work_type": _clean_string(row.get("work_type")),
        "status": _clean_string(row.get("current_status") or row.get("status")),
        "filing_date": filing_date,
        "latest_status_date": latest_status_date,
        "estimated_cost": _to_decimal(row.get("estimated_cost")),
        "raw": row,
    }
    return normalized


def normalize_dob_violation(row: Dict[str, Any]) -> Dict[str, Any]:
    # TODO: Implement real normalization.
    return {"raw": row}


def normalize_hpd_violation(row: Dict[str, Any]) -> Dict[str, Any]:
    # TODO: Implement real normalization.
    return {"raw": row}


def normalize_hpd_registration(row: Dict[str, Any]) -> Dict[str, Any]:
    # TODO: Implement real normalization.
    return {"raw": row}


def normalize_acris_legal(row: Dict[str, Any]) -> Dict[str, Any]:
    # TODO: Implement real normalization.
    return {"raw": row}


def normalize_acris_mortgage(row: Dict[str, Any]) -> Dict[str, Any]:
    # TODO: Implement real normalization.
    return {"raw": row}


def normalize_pluto(row: Dict[str, Any]) -> Dict[str, Any]:
    bbl = _clean_string(row.get("bbl"))
    block = _to_int(_first_nonempty(row, ("block", "block_", "block_num")))
    lot = _to_int(_first_nonempty(row, ("lot", "lot_", "lot_num")))
    borough_raw = _first_nonempty(row, ("borough", "boro", "borocode"))
    borough_code, _ = normalize_borough(borough_raw)
    if not bbl and borough_code:
        bbl = normalize_bbl(borough_code, block, lot)
    if not bbl:
        return {}

    addr = normalize_address(
        _first_nonempty(row, ("house", "housenum", "addressnumber")),
        _first_nonempty(row, ("street", "street_name", "streetname")),
    )
    house = addr.house_number
    street = addr.street
    zipcode = _clean_string(row.get("zipcode") or row.get("zip"))
    landuse = _clean_string(row.get("landuse") or row.get("land_use"))
    zoning = _clean_string(
        row.get("zoning")
        or row.get("zoneddist1")
        or row.get("zonedist1")
        or row.get("zonedistrict1")
    )

    return {
        "bbl": bbl,
        "borough": borough_code,
        "block": block,
        "lot": lot,
        "house": house,
        "street": street,
        "zipcode": zipcode,
        "landuse": landuse,
        "zoning": zoning,
        "lot_area": _to_decimal(row.get("lot_area") or row.get("lotarea")),
        "bldg_area": _to_decimal(row.get("bldg_area") or row.get("bldgarea")),
        "units_res": _to_int(row.get("units_res") or row.get("unitsres")),
        "units_rent": _to_int(row.get("units_rent") or row.get("unitsrent")),
        "year_built": _to_int(row.get("year_built") or row.get("yearbuilt")),
        "raw": row,
    }


def _first_nonempty(row: Dict[str, Any], keys) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "N/A"):
            return value
    return None


def _clean_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip()


def _parse_date(value: Any) -> str | None:
    if not value:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    cleaned = text_value.replace("Z", "")
    if "." in cleaned:
        cleaned = cleaned.split(".")[0]
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned).date().isoformat()
    except ValueError:
        return None


def _to_decimal(value: Any):
    if value in (None, ""):
        return None
    try:
        dec = Decimal(str(value))
        return dec
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_borough_code(row: Dict[str, Any]) -> Optional[str]:
    borough_value = _clean_string(
        row.get("borough") or row.get("boro") or row.get("borocode") or row.get("borocode1")
    )
    if borough_value:
        code, _ = normalize_borough(borough_value)
        if code:
            return code
    bbl = _clean_string(row.get("bbl"))
    if bbl:
        digits = re.sub(r"\D+", "", bbl)
        if digits:
            first = digits[0]
            if first in BOROUGH_CODE_TO_NAME:
                return first
    return None


def _canon_header(value: Optional[str]) -> str:
    token = (value or "").strip().lower()
    token = re.sub(r"\W+", "_", token)
    token = re.sub(r"_+", "_", token).strip("_")
    return token
