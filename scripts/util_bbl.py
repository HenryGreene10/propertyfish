from __future__ import annotations


def normalize_bbl(value: str | int | None) -> str | None:
    """
    Normalize raw BBL input into a 10-digit string (borough + block + lot).

    Removes non-digit characters and left-pads with zeros when necessary.
    Returns None when a canonical value cannot be produced.
    """
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None

    if len(digits) > 10:
        digits = digits[-10:]

    return digits.zfill(10)
