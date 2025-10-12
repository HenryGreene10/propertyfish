# API Contract (v0.1) — FastAPI

## GET /resolve?query=...
- Input: text (address/name)
- Output: {"candidates":[{"bbl":"1012700008","address":"6 E 43rd St, NY 10017"}]}

## GET /property/:bbl/summary
- Output: {... parcel/summary fields ..., "sources":[...]}

## GET /property/:bbl/zoning
- Output: {"base":["C5-3"],"overlays":["Special Midtown"],"far_notes":[...], "sources":[...]}

## GET /property/:bbl/deeds?limit=5
## GET /property/:bbl/mortgages?limit=5
## GET /property/:bbl/permits?since=YYYY-MM-DD
## GET /property/:bbl/violations?since=YYYY-MM-DD

## GET /property/:bbl/geo
- Output: GeoJSON feature for parcel + optional neighbors

## POST /chat
- Input: {"question":"...","context_bbl":"optional"}
- Output:
  {
    "answer":"Natural-language, with inline [Source • YYYY-MM-DD] tags.",
    "answer_bundle": { "facts":{...}, "tables":{...}, "sources":[...] },
    "citations":[{"label":"ACRIS","url":"...","updated":"..."}]
  }

