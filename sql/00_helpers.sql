-- borough map
CREATE TABLE IF NOT EXISTS public.borough_map (
  boro_code int PRIMARY KEY,
  boro_name text NOT NULL
);
INSERT INTO public.borough_map (boro_code, boro_name) VALUES
  (1,'MANHATTAN'),(2,'BRONX'),(3,'BROOKLYN'),(4,'QUEENS'),(5,'STATEN ISLAND')
ON CONFLICT (boro_code) DO NOTHING;

-- helpers (BBL make/parse)
CREATE OR REPLACE FUNCTION public.make_bbl(boro int, block int, lot int)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE
    WHEN boro BETWEEN 1 AND 5 AND block > 0 AND lot > 0
    THEN boro::text || lpad(block::text,5,'0') || lpad(lot::text,4,'0')
    ELSE NULL
  END
$$;

CREATE OR REPLACE FUNCTION public.parse_bbl(bbl_text text)
RETURNS TABLE (boro int, block int, lot int) LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN bbl_text ~ '^[1-5][0-9]{9}$' THEN substring(bbl_text,1,1)::int END AS boro,
         CASE WHEN bbl_text ~ '^[1-5][0-9]{9}$' THEN substring(bbl_text,2,5)::int END AS block,
         CASE WHEN bbl_text ~ '^[1-5][0-9]{9}$' THEN substring(bbl_text,7,4)::int END AS lot
$$;

-- parcels view (adds geom from lat/long)
DROP VIEW IF EXISTS public.parcels CASCADE;
CREATE VIEW public.parcels AS
SELECT p.*,
       CASE WHEN p.longitude IS NOT NULL AND p.latitude IS NOT NULL
            THEN ST_Transform(ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326), 2263)
       END AS geom
FROM public.pluto p;

-- NEW: borough string → code (MN/BK/QN/BX/SI or names)
CREATE OR REPLACE FUNCTION public.borough_to_code(boro_txt text)
RETURNS int LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE t text;
BEGIN
  IF boro_txt IS NULL THEN RETURN NULL; END IF;
  t := upper(trim(boro_txt));
  IF t ~ '^[1-5]$' THEN RETURN t::int; END IF;
  IF t IN ('MN','MAN','MANHATTAN')             THEN RETURN 1; END IF;
  IF t IN ('BX','BRONX')                        THEN RETURN 2; END IF;
  IF t IN ('BK','K','BKN','BROOKLYN')           THEN RETURN 3; END IF;
  IF t IN ('QN','Q','QUEENS')                   THEN RETURN 4; END IF;
  IF t IN ('SI','R','STATEN ISLAND','STATENIS') THEN RETURN 5; END IF;
  IF left(t,1) ~ '^[1-5]$' THEN RETURN left(t,1)::int; END IF;
  RETURN NULL;
END $$;

-- Normalize any BBL-like string to 10 digits: boro(1) + block(5) + lot(4)
CREATE OR REPLACE FUNCTION public.bbl_normalize(x text)
RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE d text; boro text; rest text; blk text; lt text; m text[];
BEGIN
  IF x IS NULL THEN RETURN NULL; END IF;

  -- keep digits only
  d := regexp_replace(x, '\D', '', 'g');

  -- already good (1 + 9 digits)
  IF d ~ '^[1-5][0-9]{9}$' THEN RETURN d; END IF;

  -- bare 7–9 digits (e.g. "100000001"): infer block (all but last 4) + lot (last 4), then pad
  IF d ~ '^[1-5][0-9]{6,9}$' THEN
    boro := substring(d,1,1);
    rest := substring(d,2);
    lt   := right(rest, 4);
    blk  := left(rest, greatest(length(rest)-4,0));
    RETURN boro || lpad(blk,5,'0') || lpad(lt,4,'0');
  END IF;

  -- separated forms like "3-12345-67", "3 12345 0067"
  m := regexp_matches(upper(x), '^\s*([1-5])\D*([0-9]{1,5})\D*([0-9]{1,4})\s*$');
  IF m IS NOT NULL THEN
    RETURN m[1] || lpad(m[2],5,'0') || lpad(m[3],4,'0');
  END IF;

  RETURN NULL;
END $$;

-- Overload: numeric → normalize
CREATE OR REPLACE FUNCTION public.bbl_normalize(x numeric)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT public.bbl_normalize(trim(to_char(x, 'FM9999999999999999990')));
$$;

-- Overload: double precision → normalize
CREATE OR REPLACE FUNCTION public.bbl_normalize(x double precision)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT public.bbl_normalize(trim(to_char(x, 'FM9999999999999999990')));
$$;

-- Overload: bigint → normalize
CREATE OR REPLACE FUNCTION public.bbl_normalize(x bigint)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT public.bbl_normalize(x::text);
$$;
