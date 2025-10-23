CREATE OR REPLACE FUNCTION public.borough_to_code(boro_txt text)
RETURNS int LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE t text;
BEGIN
  IF boro_txt IS NULL THEN RETURN NULL; END IF;
  t := upper(trim(boro_txt));
  IF t ~ '^[1-5]$' THEN RETURN t::int; END IF;
  IF t IN ('MN','MAN','MANHATTAN') THEN RETURN 1; END IF;
  IF t IN ('BX','BRONX') THEN RETURN 2; END IF;
  IF t IN ('BK','K','BKN','BROOKLYN') THEN RETURN 3; END IF;
  IF t IN ('QN','Q','QUEENS') THEN RETURN 4; END IF;
  IF t IN ('SI','R','STATEN ISLAND','STATENIS') THEN RETURN 5; END IF;
  IF left(t,1) ~ '^[1-5]$' THEN RETURN left(t,1)::int; END IF;
  RETURN NULL;
END $$;

CREATE OR REPLACE FUNCTION public.bbl_normalize(x text)
RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE d text; m text[];
BEGIN
  IF x IS NULL THEN RETURN NULL; END IF;
  d := regexp_replace(x, '\D', '', 'g');
  IF d ~ '^[1-5][0-9]{9}$' THEN RETURN d; END IF;
  m := regexp_matches(upper(x), '^\s*([1-5])\D*([0-9]{1,5})\D*([0-9]{1,4})\s*$');
  IF m IS NOT NULL THEN
    RETURN m[1] || lpad(m[2],5,'0') || lpad(m[3],4,'0');
  END IF;
  RETURN NULL;
END $$;
