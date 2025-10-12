# Data Dictionary (v0.1)

## Keys
- **BBL** (borough-block-lot, string): master join key.

## Parcel / Summary (PLUTO/MapPLUTO)
- address_std (text)
- bbl (text), borough (text), block (int), lot (int), bin (int)
- land_use (enum; PLUTO.landuse → label)
- tax_class (text; PLUTO.taxclass)
- lot_area_sqft (int; PLUTO.lotarea)
- bldg_sqft (int; PLUTO.bldgarea)
- stories (int; PLUTO.numfloors)
- year_built (int; PLUTO.yearbuilt)

## Zoning (ZoLa/DCP)
- base_districts (string[])
- overlays (string[])
- far_notes (text[]) — zoning text references (links)

## Documents (ACRIS)
- deeds_recent[]: recorded_at, doc_type, consideration, grantor, grantee, doc_id, doc_url
- mortgages_recent[]: recorded_at, amount, lender, borrower, doc_id, doc_url

## DOB
- permits_recent[]: filed_at, job_type, status, description, initial_cost
- violations_recent[]: issued_at, code, description, status

## Taxes/Assessment (phase 2)
- assessed_value, market_value, tax_year
- assessment_history[] (year, values)

## Geometry
- parcel_geom (GeoJSON)
- neighbors[]: nearby BBL within 250m

## Metadata (every response block)
- source_name, source_url, last_updated

