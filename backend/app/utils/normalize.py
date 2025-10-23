from __future__ import annotations

import re
from typing import Any, NamedTuple, Optional, Tuple

BOROUGH_CODE_TO_NAME: dict[str, str] = {
    "1": "MANHATTAN",
    "2": "BRONX",
    "3": "BROOKLYN",
    "4": "QUEENS",
    "5": "STATEN ISLAND",
}

# Map a wide range of borough aliases to their digit codes.
BOROUGH_ALIASES: dict[str, str] = {
    "1": "1",
    "01": "1",
    "MANHATTAN": "1",
    "MN": "1",
    "NEW YORK": "1",
    "NEW YORK COUNTY": "1",
    "2": "2",
    "02": "2",
    "BRONX": "2",
    "BX": "2",
    "THE BRONX": "2",
    "3": "3",
    "03": "3",
    "BROOKLYN": "3",
    "BK": "3",
    "KINGS": "3",
    "KINGS COUNTY": "3",
    "4": "4",
    "04": "4",
    "QUEENS": "4",
    "QN": "4",
    "QNS": "4",
    "5": "5",
    "05": "5",
    "STATEN ISLAND": "5",
    "SI": "5",
    "RICHMOND": "5",
    "RICHMOND COUNTY": "5",
}


class NormalizedAddress(NamedTuple):
    house_number: Optional[str]
    street: Optional[str]
    full: Optional[str]


def _only_digits(value: Any) -> str:
    if value in (None, ""):
        return ""
    token = str(value).strip()
    if not token:
        return ""
    return re.sub(r"\D+", "", token)


def normalize_borough(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (borough_code, borough_name) for the given value.
    Code is the digit 1-5 string; name is the canonical uppercase name.
    """
    if value in (None, ""):
        return None, None
    token = str(value).strip()
    if not token:
        return None, None

    digits = _only_digits(token)
    if digits:
        code = digits[0]
        if code in BOROUGH_CODE_TO_NAME:
            return code, BOROUGH_CODE_TO_NAME[code]

    upper = token.upper()
    code = BOROUGH_ALIASES.get(upper)
    if code:
        return code, BOROUGH_CODE_TO_NAME[code]
    return None, None


def _parse_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    digits = _only_digits(value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def normalize_bbl(borough: Any, block: Any, lot: Any) -> Optional[str]:
    """
    Produce a canonical 10-digit BBL string from borough/block/lot inputs.
    Falls back to any direct 10-digit candidates embedded in the inputs.
    """
    for candidate in (borough, block, lot):
        digits = _only_digits(candidate)
        if len(digits) == 10:
            return digits

    borough_code, _ = normalize_borough(borough)
    block_int = _parse_int(block)
    lot_int = _parse_int(lot)
    if not borough_code or block_int is None or lot_int is None:
        return None
    return f"{borough_code}{block_int:05d}{lot_int:04d}"


def _normalize_house_number(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    token = str(value).strip().upper()
    if not token:
        return None

    token = token.replace(" ", "")
    if "-" in token:
        parts = token.split("-")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            left = str(int(parts[0]))
            right = f"{int(parts[1]):02d}"
            return f"{left}-{right}"

    cleaned = "".join(ch for ch in token if ch.isalnum())
    if not cleaned:
        return None
    if cleaned.isdigit():
        return str(int(cleaned))
    return cleaned


def _normalize_street(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    token = str(value).upper()
    token = re.sub(r"[^\w\s]", " ", token)
    token = re.sub(r"\s+", " ", token).strip()
    return token or None


def normalize_address(house_number: Any, street: Any) -> NormalizedAddress:
    """
    Normalize house/street tokens for deterministic joins.
    Returns uppercase street and trimmed house number (Queens-style hyphen preserved).
    """
    house = _normalize_house_number(house_number)
    street_norm = _normalize_street(street)
    components = [comp for comp in (house, street_norm) if comp]
    full = " ".join(components) if components else None
    return NormalizedAddress(house, street_norm, full)


__all__ = [
    "BOROUGH_ALIASES",
    "BOROUGH_CODE_TO_NAME",
    "NormalizedAddress",
    "normalize_address",
    "normalize_bbl",
    "normalize_borough",
]
