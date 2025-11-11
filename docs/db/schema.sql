--
-- PostgreSQL database dump
--

\restrict Ode7sqBJWe6cMoFW607YWBbWC7dViGIzFrFnevgaHqmWHQIi2gfDIljvevYgqAg

-- Dumped from database version 16.4 (Debian 16.4-1.pgdg110+2)
-- Dumped by pg_dump version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: tiger; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger;


--
-- Name: tiger_data; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger_data;


--
-- Name: topology; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA topology;


--
-- Name: SCHEMA topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA topology IS 'PostGIS Topology schema';


--
-- Name: fuzzystrmatch; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch WITH SCHEMA public;


--
-- Name: EXTENSION fuzzystrmatch; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION fuzzystrmatch IS 'determine similarities and distance between strings';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_tiger_geocoder; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder WITH SCHEMA tiger;


--
-- Name: EXTENSION postgis_tiger_geocoder; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_tiger_geocoder IS 'PostGIS tiger geocoder and reverse geocoder';


--
-- Name: postgis_topology; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;


--
-- Name: EXTENSION postgis_topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_topology IS 'PostGIS topology spatial types and functions';


--
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- Name: _addr_norm(text, text, smallint, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._addr_norm(hn text, st text, b smallint, z text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT lower(regexp_replace(
    coalesce(hn,'') || ' ' ||
    CASE b WHEN 1 THEN 'manhattan' WHEN 2 THEN 'bronx' WHEN 3 THEN 'brooklyn'
           WHEN 4 THEN 'queens' WHEN 5 THEN 'staten island' END || ' ' ||
    coalesce(st,'') || ' ' || coalesce(z,''),
    '\s+', ' ', 'g'))
$$;


--
-- Name: bbl_normalize(double precision); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.bbl_normalize(x double precision) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT public.bbl_normalize(trim(to_char(x, 'FM9999999999999999990')));
$$;


--
-- Name: bbl_normalize(bigint); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.bbl_normalize(x bigint) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT public.bbl_normalize(x::text);
$$;


--
-- Name: bbl_normalize(numeric); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.bbl_normalize(x numeric) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT public.bbl_normalize(trim(to_char(x, 'FM9999999999999999990')));
$$;


--
-- Name: bbl_normalize(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.bbl_normalize(x text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $_$
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
END $_$;


--
-- Name: borough_to_code(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.borough_to_code(boro_txt text) RETURNS integer
    LANGUAGE plpgsql IMMUTABLE
    AS $_$
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
END $_$;


--
-- Name: make_bbl(integer, integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_bbl(boro integer, block integer, lot integer) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT CASE
    WHEN boro BETWEEN 1 AND 5 AND block > 0 AND lot > 0
    THEN boro::text || lpad(block::text,5,'0') || lpad(lot::text,4,'0')
    ELSE NULL
  END
$$;


--
-- Name: norm_bbl_text(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.norm_bbl_text(v text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
  SELECT CASE
           WHEN v IS NULL THEN NULL
           ELSE lpad(regexp_replace(v, '\D', '', 'g'), 10, '0')
         END
$$;


--
-- Name: parse_bbl(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.parse_bbl(bbl_text text) RETURNS TABLE(boro integer, block integer, lot integer)
    LANGUAGE sql IMMUTABLE
    AS $_$
  SELECT CASE WHEN bbl_text ~ '^[1-5][0-9]{9}$' THEN substring(bbl_text,1,1)::int END AS boro,
         CASE WHEN bbl_text ~ '^[1-5][0-9]{9}$' THEN substring(bbl_text,2,5)::int END AS block,
         CASE WHEN bbl_text ~ '^[1-5][0-9]{9}$' THEN substring(bbl_text,7,4)::int END AS lot
$_$;


--
-- Name: upsert_addresses_from_pluto(); Type: PROCEDURE; Schema: public; Owner: -
--

CREATE PROCEDURE public.upsert_addresses_from_pluto()
    LANGUAGE sql
    AS $$
  INSERT INTO dim_address(house_no, street, borough, zipcode, full_norm, full_display)
  SELECT DISTINCT d.house_no, d.street, d.borough, d.zipcode,
         _addr_norm(d.house_no, d.street, d.borough, d.zipcode) AS full_norm,
         d.address AS full_display
  FROM stg_pluto_derived d
  WHERE d.house_no IS NOT NULL AND d.street IS NOT NULL
  ON CONFLICT (full_norm) DO NOTHING;
$$;


--
-- Name: upsert_parcels_from_pluto(); Type: PROCEDURE; Schema: public; Owner: -
--

CREATE PROCEDURE public.upsert_parcels_from_pluto()
    LANGUAGE sql
    AS $$
  INSERT INTO dim_parcel(bbl, bin, borough, block, lot, addr_id)
  SELECT d.bbl, NULL::bigint, d.borough, d.block, d.lot, a.addr_id
  FROM stg_pluto_derived d
  JOIN dim_address a
    ON a.full_norm = _addr_norm(d.house_no, d.street, d.borough, d.zipcode)
  ON CONFLICT (bbl) DO UPDATE
    SET addr_id = EXCLUDED.addr_id,
        borough = EXCLUDED.borough,
        block   = EXCLUDED.block,
        lot     = EXCLUDED.lot,
        updated_at = now();
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acris_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acris_events (
    id bigint NOT NULL,
    bbl text,
    doc_type text,
    recorded_at date,
    consideration numeric,
    parties jsonb,
    doc_id text,
    doc_url text,
    last_updated timestamp without time zone
);


--
-- Name: acris_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acris_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acris_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acris_events_id_seq OWNED BY public.acris_events.id;


--
-- Name: acris_legal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acris_legal (
    doc_id text NOT NULL,
    bbl text,
    doc_type text,
    recorded_date date,
    raw jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: acris_mortgage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acris_mortgage (
    doc_id text NOT NULL,
    bbl text,
    doc_type text,
    recorded_date date,
    amount numeric,
    raw jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: borough_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.borough_map (
    boro_code integer NOT NULL,
    boro_name text NOT NULL
);


--
-- Name: dim_address; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_address (
    addr_id bigint NOT NULL,
    house_no text,
    street text,
    unit text,
    borough smallint,
    zipcode text,
    full_norm text,
    full_display text
);


--
-- Name: dim_address_addr_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dim_address_addr_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dim_address_addr_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dim_address_addr_id_seq OWNED BY public.dim_address.addr_id;


--
-- Name: dim_parcel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_parcel (
    parcel_id bigint NOT NULL,
    bbl bigint NOT NULL,
    bin bigint,
    borough smallint NOT NULL,
    block integer NOT NULL,
    lot integer NOT NULL,
    addr_id bigint,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: dim_parcel_parcel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dim_parcel_parcel_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dim_parcel_parcel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dim_parcel_parcel_id_seq OWNED BY public.dim_parcel.parcel_id;


--
-- Name: dob_complaints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dob_complaints (
    complaint_id text NOT NULL,
    bbl text,
    bin text,
    borough text,
    house_number text,
    street text,
    zip text,
    apartment text,
    community_board text,
    complaint_category text,
    complaint_type text,
    status text,
    priority text,
    disposition text,
    inspector text,
    date_received timestamp with time zone,
    last_inspection_date timestamp with time zone,
    last_status_date timestamp with time zone,
    latitude double precision,
    longitude double precision,
    source_version text DEFAULT 'dob_complaints_v1'::text,
    raw jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    date_entered timestamp with time zone,
    house_street text,
    zip_code text,
    inspection_date timestamp with time zone,
    disposition_date timestamp with time zone,
    dobrundate timestamp with time zone
);


--
-- Name: dob_complaints__staging; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dob_complaints__staging (
    complaint_id text NOT NULL,
    bbl text,
    bin text,
    borough text,
    house_number text,
    street text,
    zip text,
    apartment text,
    community_board text,
    complaint_category text,
    complaint_type text,
    status text,
    priority text,
    disposition text,
    inspector text,
    date_received timestamp with time zone,
    last_inspection_date timestamp with time zone,
    last_status_date timestamp with time zone,
    latitude double precision,
    longitude double precision,
    source_version text,
    raw jsonb NOT NULL,
    loaded_at timestamp with time zone DEFAULT now()
);


--
-- Name: dob_permits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dob_permits (
    id integer NOT NULL,
    bbl text,
    job_number text,
    status text,
    filed_date date,
    status_date date,
    source_url text,
    filing_date date,
    latest_status_date date,
    estimated_cost numeric,
    raw jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    borough text,
    houseno text,
    street text,
    latitude double precision,
    longitude double precision,
    issuance_date date GENERATED ALWAYS AS (COALESCE(filing_date, filed_date, status_date, latest_status_date)) STORED,
    job_type text,
    description text,
    last_update text,
    source_row_id text
);


--
-- Name: dob_permits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dob_permits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dob_permits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dob_permits_id_seq OWNED BY public.dob_permits.id;


--
-- Name: dob_violations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dob_violations (
    id integer NOT NULL,
    bbl text,
    violation_number text,
    status text,
    issue_date date,
    source_url text,
    disposition_date date,
    raw jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    borough text,
    houseno text,
    street text,
    latitude double precision,
    longitude double precision
);


--
-- Name: dob_violations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dob_violations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dob_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dob_violations_id_seq OWNED BY public.dob_violations.id;


--
-- Name: hpd_registrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hpd_registrations (
    registration_id text NOT NULL,
    bbl text,
    house_no text,
    street_name text,
    borough text,
    registration_date date,
    raw jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: hpd_violations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hpd_violations (
    violation_id text NOT NULL,
    bbl text,
    house_no text,
    street_name text,
    borough text,
    status text,
    inspection_date date,
    disposition_date date,
    raw jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ingest_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingest_runs (
    run_id bigint NOT NULL,
    source text NOT NULL,
    version text DEFAULT 'dob_permits_v1'::text NOT NULL,
    status text NOT NULL,
    started_at timestamp with time zone DEFAULT now(),
    finished_at timestamp with time zone,
    inserted_rows bigint DEFAULT 0,
    file_sha256 text,
    log_tail text,
    rows_inserted integer DEFAULT 0,
    rows_updated integer DEFAULT 0,
    notes text,
    error text,
    CONSTRAINT ingest_runs_status_check CHECK ((status = ANY (ARRAY['running'::text, 'success'::text, 'failed'::text])))
);


--
-- Name: ingest_runs_run_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ingest_runs_run_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ingest_runs_run_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ingest_runs_run_id_seq OWNED BY public.ingest_runs.run_id;


--
-- Name: ingestion_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingestion_alerts (
    id bigint NOT NULL,
    source text NOT NULL,
    level text DEFAULT 'warn'::text NOT NULL,
    summary text NOT NULL,
    details jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone
);


--
-- Name: ingestion_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ingestion_alerts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ingestion_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ingestion_alerts_id_seq OWNED BY public.ingestion_alerts.id;


--
-- Name: ingestion_watermarks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingestion_watermarks (
    source text NOT NULL,
    last_cursor text,
    last_seen_at timestamp with time zone,
    last_run timestamp with time zone,
    notes text,
    window_start date,
    window_end date,
    last_offset integer DEFAULT 0 NOT NULL
);


--
-- Name: mv_permit_agg; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_permit_agg AS
 SELECT (public.bbl_normalize(bbl))::bigint AS bbl_norm,
    max(issuance_date) AS last_permit_date,
    count(*) FILTER (WHERE (issuance_date >= (CURRENT_DATE - '365 days'::interval))) AS permit_count_12m
   FROM public.dob_permits
  GROUP BY (public.bbl_normalize(bbl))::bigint
  WITH NO DATA;


--
-- Name: mv_property_events__dob_complaints; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_property_events__dob_complaints AS
 SELECT bbl,
    count(*) AS complaints_total,
    count(*) FILTER (WHERE (date_received >= (now() - '365 days'::interval))) AS complaints_1y,
    max(date_received) AS complaints_most_recent
   FROM public.dob_complaints
  WHERE (bbl IS NOT NULL)
  GROUP BY bbl
  WITH NO DATA;


--
-- Name: pad_bin_bbl; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pad_bin_bbl (
    bin text NOT NULL,
    bbl text NOT NULL
);


--
-- Name: pluto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pluto (
    id bigint NOT NULL,
    bbl text NOT NULL,
    address text,
    zipcode text,
    borough text,
    houseno text,
    street text,
    latitude double precision,
    longitude double precision,
    raw jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: parcels; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.parcels AS
 SELECT id,
    bbl,
    address,
    zipcode,
    borough,
    houseno,
    street,
    latitude,
    longitude,
    raw,
    updated_at,
        CASE
            WHEN ((longitude IS NOT NULL) AND (latitude IS NOT NULL)) THEN public.st_transform(public.st_setsrid(public.st_makepoint(longitude, latitude), 4326), 2263)
            ELSE NULL::public.geometry
        END AS geom
   FROM public.pluto p;


--
-- Name: permits_norm; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.permits_norm AS
 WITH src AS (
         SELECT NULLIF(TRIM(BOTH FROM dob_permits.job_number), ''::text) AS job_number,
            upper(NULLIF(TRIM(BOTH FROM dob_permits.bbl), ''::text)) AS bbl_text,
            (NULLIF((dob_permits.filed_date)::text, ''::text))::date AS filed_date,
            (NULLIF((dob_permits.filing_date)::text, ''::text))::date AS filing_date,
            (NULLIF((dob_permits.issuance_date)::text, ''::text))::date AS issuance_date,
            (NULLIF((dob_permits.status_date)::text, ''::text))::date AS status_date,
            (NULLIF((dob_permits.latest_status_date)::text, ''::text))::date AS latest_status_date,
            NULLIF(TRIM(BOTH FROM dob_permits.status), ''::text) AS status,
            dob_permits.estimated_cost,
            NULL::integer AS boro_code,
            NULL::integer AS block,
            NULL::integer AS lot,
            NULL::text AS house_no,
            NULL::text AS street_name,
            NULL::double precision AS latitude,
            NULL::double precision AS longitude
           FROM public.dob_permits
        ), parts AS (
         SELECT s.job_number,
            s.bbl_text,
            s.filed_date,
            s.filing_date,
            s.issuance_date,
            s.status_date,
            s.latest_status_date,
            s.status,
            s.estimated_cost,
            s.boro_code,
            s.block,
            s.lot,
            s.house_no,
            s.street_name,
            s.latitude,
            s.longitude,
            (public.parse_bbl(s.bbl_text)).boro AS boro_code_d,
            (public.parse_bbl(s.bbl_text)).block AS block_d,
            (public.parse_bbl(s.bbl_text)).lot AS lot_d
           FROM src s
        )
 SELECT p.job_number,
    COALESCE(p.bbl_text, public.make_bbl(p.boro_code, p.block, p.lot)) AS bbl_text,
    COALESCE(p.boro_code, p.boro_code_d) AS boro_code,
    COALESCE(p.block, p.block_d) AS block,
    COALESCE(p.lot, p.lot_d) AS lot,
    p.house_no,
    p.street_name,
    p.filed_date,
    p.filing_date,
    p.issuance_date,
    COALESCE(p.issuance_date, p.filing_date, p.filed_date, p.status_date, p.latest_status_date) AS issuance_date_norm,
    p.status_date,
    p.latest_status_date,
    p.status,
    p.latitude,
    p.longitude,
    bm.boro_name,
        CASE
            WHEN ((p.house_no IS NULL) AND (p.street_name IS NULL)) THEN NULL::text
            ELSE ((upper(regexp_replace(((COALESCE(p.house_no, ''::text) || ' '::text) || COALESCE(p.street_name, ''::text)), '\s+'::text, ' '::text, 'g'::text)) || ' | '::text) || COALESCE(bm.boro_name, ''::text))
        END AS address_key
   FROM (parts p
     LEFT JOIN public.borough_map bm ON ((bm.boro_code = COALESCE(p.boro_code, p.boro_code_d))));


--
-- Name: permits_violations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permits_violations (
    id bigint NOT NULL,
    bbl text,
    kind text,
    status text,
    filed_at date,
    closed_at date,
    details jsonb,
    last_updated timestamp without time zone
);


--
-- Name: permits_violations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.permits_violations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: permits_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.permits_violations_id_seq OWNED BY public.permits_violations.id;


--
-- Name: pluto_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pluto_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pluto_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pluto_id_seq OWNED BY public.pluto.id;


--
-- Name: pluto_staging; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pluto_staging (
    rowhash text NOT NULL,
    bbl text,
    address text,
    zipcode text,
    borough text,
    houseno text,
    street text,
    latitude double precision,
    longitude double precision,
    raw jsonb
);


--
-- Name: properties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.properties (
    bbl text NOT NULL,
    address text,
    normalized_address text,
    owner_name text,
    year_built integer,
    units_res integer
);


--
-- Name: property_rollup; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.property_rollup AS
 SELECT COALESCE(p.bbl, v.bbl) AS bbl,
    count(p.job_number) FILTER (WHERE (p.filing_date >= (CURRENT_DATE - '365 days'::interval))) AS permits_last_12m,
    count(v.violation_number) FILTER (WHERE (v.status ~~* 'OPEN%'::text)) AS open_violations
   FROM (public.dob_permits p
     FULL JOIN public.dob_violations v ON ((p.bbl = v.bbl)))
  GROUP BY COALESCE(p.bbl, v.bbl)
  WITH NO DATA;


--
-- Name: property_search_base; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.property_search_base AS
 SELECT p.parcel_id,
    p.bbl,
    a.full_display AS address
   FROM (public.dim_parcel p
     LEFT JOIN public.dim_address a ON ((a.addr_id = p.addr_id)))
  WITH NO DATA;


--
-- Name: property_search; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.property_search AS
 WITH psb AS (
         SELECT property_search_base.address,
            (NULLIF(regexp_replace((property_search_base.bbl)::text, '\..*'::text, ''::text), ''::text))::bigint AS bbl
           FROM public.property_search_base
        ), pa AS (
         SELECT mv_permit_agg.bbl_norm,
            mv_permit_agg.permit_count_12m,
            mv_permit_agg.last_permit_date
           FROM public.mv_permit_agg
        ), p_enriched AS (
         SELECT psb.address,
            psb.bbl,
            SUBSTRING(lpad((psb.bbl)::text, 10, '0'::text) FROM 1 FOR 1) AS boro_digit
           FROM psb
        )
 SELECT COALESCE(NULLIF(upper(TRIM(BOTH FROM ((COALESCE(p.houseno, ''::text) || ' '::text) || p.street))), ''::text), e.address) AS address,
    e.bbl,
        CASE e.boro_digit
            WHEN '1'::text THEN 'MN'::text
            WHEN '2'::text THEN 'BX'::text
            WHEN '3'::text THEN 'BK'::text
            WHEN '4'::text THEN 'QN'::text
            WHEN '5'::text THEN 'SI'::text
            ELSE NULL::text
        END AS borough,
    COALESCE(a.permit_count_12m, (0)::bigint) AS permit_count_12m,
    a.last_permit_date,
    pp.year_built AS year_built,
        CASE e.boro_digit
            WHEN '1'::text THEN 'Manhattan'::text
            WHEN '2'::text THEN 'Bronx'::text
            WHEN '3'::text THEN 'Brooklyn'::text
            WHEN '4'::text THEN 'Queens'::text
            WHEN '5'::text THEN 'Staten Island'::text
            ELSE NULL::text
        END AS borough_full
   FROM (((p_enriched e
     LEFT JOIN public.pluto p ON (((NULLIF(regexp_replace(p.bbl, '\..*'::text, ''::text), ''::text))::bigint = e.bbl)))
     LEFT JOIN public.properties pp ON ((pp.bbl = e.bbl)))
     LEFT JOIN pa a ON ((e.bbl = a.bbl_norm)))
  WITH NO DATA;


--
-- Name: staging_acris_legal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_acris_legal (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_acris_legal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_acris_legal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_acris_legal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_acris_legal_id_seq OWNED BY public.staging_acris_legal.id;


--
-- Name: staging_acris_master; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_acris_master (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_acris_master_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_acris_master_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_acris_master_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_acris_master_id_seq OWNED BY public.staging_acris_master.id;


--
-- Name: staging_acris_mortgage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_acris_mortgage (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_acris_mortgage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_acris_mortgage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_acris_mortgage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_acris_mortgage_id_seq OWNED BY public.staging_acris_mortgage.id;


--
-- Name: staging_dob_permits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_dob_permits (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_dob_permits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_dob_permits_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_dob_permits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_dob_permits_id_seq OWNED BY public.staging_dob_permits.id;


--
-- Name: staging_dob_violations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_dob_violations (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_dob_violations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_dob_violations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_dob_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_dob_violations_id_seq OWNED BY public.staging_dob_violations.id;


--
-- Name: staging_hpd_registrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_hpd_registrations (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_hpd_registrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_hpd_registrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_hpd_registrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_hpd_registrations_id_seq OWNED BY public.staging_hpd_registrations.id;


--
-- Name: staging_hpd_violations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_hpd_violations (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_hpd_violations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_hpd_violations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_hpd_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_hpd_violations_id_seq OWNED BY public.staging_hpd_violations.id;


--
-- Name: staging_pluto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_pluto (
    id bigint NOT NULL,
    source_pk text NOT NULL,
    payload jsonb NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    row_hash text NOT NULL
);


--
-- Name: staging_pluto_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_pluto_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_pluto_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_pluto_id_seq OWNED BY public.staging_pluto.id;


--
-- Name: stg_pluto_25v2_1; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stg_pluto_25v2_1 (
    bbl bigint,
    bin bigint,
    address text,
    house_no text,
    street text,
    zipcode text,
    borough smallint,
    block integer,
    lot integer,
    _file_sha256 text,
    _ingested_at timestamp with time zone DEFAULT now()
);


--
-- Name: stg_pluto_derived; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.stg_pluto_derived AS
 SELECT bbl,
    address,
    zipcode,
    borough,
    block,
    lot,
        CASE
            WHEN (address ~ '^\s*\d+'::text) THEN split_part(address, ' '::text, 1)
            ELSE NULL::text
        END AS house_no,
        CASE
            WHEN (POSITION((' '::text) IN (address)) > 0) THEN substr(address, (POSITION((' '::text) IN (address)) + 1))
            ELSE NULL::text
        END AS street
   FROM public.stg_pluto_25v2_1;


--
-- Name: vw_permits_norm; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_permits_norm AS
 SELECT job_number,
    status,
    issuance_date,
    filing_date,
    filed_date,
    status_date,
    COALESCE(issuance_date, filing_date, filed_date, status_date) AS event_date,
        CASE
            WHEN (bbl IS NOT NULL) THEN (replace(split_part(bbl, '.'::text, 1), ' '::text, ''::text))::bigint
            ELSE NULL::bigint
        END AS bbl_norm
   FROM public.dob_permits p;


--
-- Name: vw_violations_norm; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_violations_norm AS
 WITH src AS (
         SELECT upper(NULLIF(TRIM(BOTH FROM dob_violations.violation_number), ''::text)) AS violation_number,
            upper(NULLIF(TRIM(BOTH FROM dob_violations.bbl), ''::text)) AS bbl_text,
            (NULLIF((dob_violations.issue_date)::text, ''::text))::date AS issue_date,
            (NULLIF((dob_violations.disposition_date)::text, ''::text))::date AS disposition_date,
            NULLIF(TRIM(BOTH FROM dob_violations.status), ''::text) AS status,
            NULL::integer AS boro_code,
            NULL::integer AS block,
            NULL::integer AS lot,
            NULL::text AS house_no,
            NULL::text AS street_name,
            NULL::double precision AS latitude,
            NULL::double precision AS longitude
           FROM public.dob_violations
        ), parts AS (
         SELECT s.violation_number,
            s.bbl_text,
            s.issue_date,
            s.disposition_date,
            s.status,
            s.boro_code,
            s.block,
            s.lot,
            s.house_no,
            s.street_name,
            s.latitude,
            s.longitude,
            (public.parse_bbl(s.bbl_text)).boro AS boro_code_d,
            (public.parse_bbl(s.bbl_text)).block AS block_d,
            (public.parse_bbl(s.bbl_text)).lot AS lot_d
           FROM src s
        )
 SELECT p.violation_number,
    COALESCE(p.bbl_text, public.make_bbl(p.boro_code, p.block, p.lot)) AS bbl_text,
    COALESCE(p.boro_code, p.boro_code_d) AS boro_code,
    COALESCE(p.block, p.block_d) AS block,
    COALESCE(p.lot, p.lot_d) AS lot,
    p.house_no,
    p.street_name,
    p.issue_date,
    p.disposition_date,
    p.status,
    p.latitude,
    p.longitude,
    bm.boro_name,
        CASE
            WHEN ((p.house_no IS NULL) AND (p.street_name IS NULL)) THEN NULL::text
            ELSE ((upper(regexp_replace(((COALESCE(p.house_no, ''::text) || ' '::text) || COALESCE(p.street_name, ''::text)), '\s+'::text, ' '::text, 'g'::text)) || ' | '::text) || COALESCE(bm.boro_name, ''::text))
        END AS address_key
   FROM (parts p
     LEFT JOIN public.borough_map bm ON ((bm.boro_code = COALESCE(p.boro_code, p.boro_code_d))));


--
-- Name: zoning; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zoning (
    id integer NOT NULL,
    bbl text,
    district text
);


--
-- Name: zoning_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.zoning_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zoning_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.zoning_id_seq OWNED BY public.zoning.id;


--
-- Name: zoning_layers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zoning_layers (
    bbl text NOT NULL,
    base_codes text[],
    overlays text[],
    sp_districts text[],
    far_notes text,
    last_updated timestamp without time zone
);


--
-- Name: acris_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acris_events ALTER COLUMN id SET DEFAULT nextval('public.acris_events_id_seq'::regclass);


--
-- Name: dim_address addr_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_address ALTER COLUMN addr_id SET DEFAULT nextval('public.dim_address_addr_id_seq'::regclass);


--
-- Name: dim_parcel parcel_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_parcel ALTER COLUMN parcel_id SET DEFAULT nextval('public.dim_parcel_parcel_id_seq'::regclass);


--
-- Name: dob_permits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_permits ALTER COLUMN id SET DEFAULT nextval('public.dob_permits_id_seq'::regclass);


--
-- Name: dob_violations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_violations ALTER COLUMN id SET DEFAULT nextval('public.dob_violations_id_seq'::regclass);


--
-- Name: ingest_runs run_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingest_runs ALTER COLUMN run_id SET DEFAULT nextval('public.ingest_runs_run_id_seq'::regclass);


--
-- Name: ingestion_alerts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingestion_alerts ALTER COLUMN id SET DEFAULT nextval('public.ingestion_alerts_id_seq'::regclass);


--
-- Name: permits_violations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permits_violations ALTER COLUMN id SET DEFAULT nextval('public.permits_violations_id_seq'::regclass);


--
-- Name: pluto id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pluto ALTER COLUMN id SET DEFAULT nextval('public.pluto_id_seq'::regclass);


--
-- Name: staging_acris_legal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_legal ALTER COLUMN id SET DEFAULT nextval('public.staging_acris_legal_id_seq'::regclass);


--
-- Name: staging_acris_master id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_master ALTER COLUMN id SET DEFAULT nextval('public.staging_acris_master_id_seq'::regclass);


--
-- Name: staging_acris_mortgage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_mortgage ALTER COLUMN id SET DEFAULT nextval('public.staging_acris_mortgage_id_seq'::regclass);


--
-- Name: staging_dob_permits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_dob_permits ALTER COLUMN id SET DEFAULT nextval('public.staging_dob_permits_id_seq'::regclass);


--
-- Name: staging_dob_violations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_dob_violations ALTER COLUMN id SET DEFAULT nextval('public.staging_dob_violations_id_seq'::regclass);


--
-- Name: staging_hpd_registrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_hpd_registrations ALTER COLUMN id SET DEFAULT nextval('public.staging_hpd_registrations_id_seq'::regclass);


--
-- Name: staging_hpd_violations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_hpd_violations ALTER COLUMN id SET DEFAULT nextval('public.staging_hpd_violations_id_seq'::regclass);


--
-- Name: staging_pluto id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_pluto ALTER COLUMN id SET DEFAULT nextval('public.staging_pluto_id_seq'::regclass);


--
-- Name: zoning id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zoning ALTER COLUMN id SET DEFAULT nextval('public.zoning_id_seq'::regclass);


--
-- Name: acris_events acris_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acris_events
    ADD CONSTRAINT acris_events_pkey PRIMARY KEY (id);


--
-- Name: acris_legal acris_legal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acris_legal
    ADD CONSTRAINT acris_legal_pkey PRIMARY KEY (doc_id);


--
-- Name: acris_mortgage acris_mortgage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acris_mortgage
    ADD CONSTRAINT acris_mortgage_pkey PRIMARY KEY (doc_id);


--
-- Name: borough_map borough_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.borough_map
    ADD CONSTRAINT borough_map_pkey PRIMARY KEY (boro_code);


--
-- Name: dim_address dim_address_full_norm_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_address
    ADD CONSTRAINT dim_address_full_norm_key UNIQUE (full_norm);


--
-- Name: dim_address dim_address_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_address
    ADD CONSTRAINT dim_address_pkey PRIMARY KEY (addr_id);


--
-- Name: dim_parcel dim_parcel_bbl_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_parcel
    ADD CONSTRAINT dim_parcel_bbl_key UNIQUE (bbl);


--
-- Name: dim_parcel dim_parcel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_parcel
    ADD CONSTRAINT dim_parcel_pkey PRIMARY KEY (parcel_id);


--
-- Name: dob_complaints__staging dob_complaints__staging_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_complaints__staging
    ADD CONSTRAINT dob_complaints__staging_pkey PRIMARY KEY (complaint_id);


--
-- Name: dob_complaints dob_complaints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_complaints
    ADD CONSTRAINT dob_complaints_pkey PRIMARY KEY (complaint_id);


--
-- Name: dob_permits dob_permits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_permits
    ADD CONSTRAINT dob_permits_pkey PRIMARY KEY (id);


--
-- Name: dob_violations dob_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_violations
    ADD CONSTRAINT dob_violations_pkey PRIMARY KEY (id);


--
-- Name: hpd_registrations hpd_registrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hpd_registrations
    ADD CONSTRAINT hpd_registrations_pkey PRIMARY KEY (registration_id);


--
-- Name: hpd_violations hpd_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hpd_violations
    ADD CONSTRAINT hpd_violations_pkey PRIMARY KEY (violation_id);


--
-- Name: ingest_runs ingest_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingest_runs
    ADD CONSTRAINT ingest_runs_pkey PRIMARY KEY (run_id);


--
-- Name: ingestion_alerts ingestion_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingestion_alerts
    ADD CONSTRAINT ingestion_alerts_pkey PRIMARY KEY (id);


--
-- Name: pad_bin_bbl pad_bin_bbl_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pad_bin_bbl
    ADD CONSTRAINT pad_bin_bbl_pkey PRIMARY KEY (bin);


--
-- Name: permits_violations permits_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permits_violations
    ADD CONSTRAINT permits_violations_pkey PRIMARY KEY (id);


--
-- Name: pluto pluto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pluto
    ADD CONSTRAINT pluto_pkey PRIMARY KEY (id);


--
-- Name: pluto_staging pluto_staging_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pluto_staging
    ADD CONSTRAINT pluto_staging_pkey PRIMARY KEY (rowhash);


--
-- Name: properties properties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_pkey PRIMARY KEY (bbl);


--
-- Name: staging_acris_legal staging_acris_legal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_legal
    ADD CONSTRAINT staging_acris_legal_pkey PRIMARY KEY (id);


--
-- Name: staging_acris_legal staging_acris_legal_row_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_legal
    ADD CONSTRAINT staging_acris_legal_row_hash_key UNIQUE (row_hash);


--
-- Name: staging_acris_master staging_acris_master_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_master
    ADD CONSTRAINT staging_acris_master_pkey PRIMARY KEY (id);


--
-- Name: staging_acris_mortgage staging_acris_mortgage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_mortgage
    ADD CONSTRAINT staging_acris_mortgage_pkey PRIMARY KEY (id);


--
-- Name: staging_acris_mortgage staging_acris_mortgage_row_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_acris_mortgage
    ADD CONSTRAINT staging_acris_mortgage_row_hash_key UNIQUE (row_hash);


--
-- Name: staging_dob_permits staging_dob_permits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_dob_permits
    ADD CONSTRAINT staging_dob_permits_pkey PRIMARY KEY (id);


--
-- Name: staging_dob_violations staging_dob_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_dob_violations
    ADD CONSTRAINT staging_dob_violations_pkey PRIMARY KEY (id);


--
-- Name: staging_hpd_registrations staging_hpd_registrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_hpd_registrations
    ADD CONSTRAINT staging_hpd_registrations_pkey PRIMARY KEY (id);


--
-- Name: staging_hpd_registrations staging_hpd_registrations_row_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_hpd_registrations
    ADD CONSTRAINT staging_hpd_registrations_row_hash_key UNIQUE (row_hash);


--
-- Name: staging_hpd_violations staging_hpd_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_hpd_violations
    ADD CONSTRAINT staging_hpd_violations_pkey PRIMARY KEY (id);


--
-- Name: staging_hpd_violations staging_hpd_violations_row_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_hpd_violations
    ADD CONSTRAINT staging_hpd_violations_row_hash_key UNIQUE (row_hash);


--
-- Name: staging_pluto staging_pluto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_pluto
    ADD CONSTRAINT staging_pluto_pkey PRIMARY KEY (id);


--
-- Name: staging_pluto staging_pluto_row_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_pluto
    ADD CONSTRAINT staging_pluto_row_hash_key UNIQUE (row_hash);


--
-- Name: dob_permits uq_dob_permits_job_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_permits
    ADD CONSTRAINT uq_dob_permits_job_number UNIQUE (job_number);


--
-- Name: ingestion_watermarks ux_ingestion_watermarks_source_window; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingestion_watermarks
    ADD CONSTRAINT ux_ingestion_watermarks_source_window UNIQUE (source, window_start);


--
-- Name: zoning_layers zoning_layers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zoning_layers
    ADD CONSTRAINT zoning_layers_pkey PRIMARY KEY (bbl);


--
-- Name: zoning zoning_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zoning
    ADD CONSTRAINT zoning_pkey PRIMARY KEY (id);


--
-- Name: idx_acris_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_acris_bbl ON public.acris_events USING btree (bbl);


--
-- Name: idx_acris_legal_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_acris_legal_bbl ON public.acris_legal USING btree (bbl);


--
-- Name: idx_acris_mortgage_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_acris_mortgage_bbl ON public.acris_mortgage USING btree (bbl);


--
-- Name: idx_acris_rec; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_acris_rec ON public.acris_events USING btree (recorded_at DESC);


--
-- Name: idx_dob_complaints_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_bbl ON public.dob_complaints USING btree (bbl);


--
-- Name: idx_dob_complaints_date_entered; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_date_entered ON public.dob_complaints USING btree (date_entered);


--
-- Name: idx_dob_complaints_date_received; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_date_received ON public.dob_complaints USING btree (date_received);


--
-- Name: idx_dob_complaints_disposition; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_disposition ON public.dob_complaints USING btree (disposition_date);


--
-- Name: idx_dob_complaints_house_street; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_house_street ON public.dob_complaints USING btree (house_street);


--
-- Name: idx_dob_complaints_inspection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_inspection ON public.dob_complaints USING btree (inspection_date);


--
-- Name: idx_dob_complaints_last_status_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_last_status_date ON public.dob_complaints USING btree (last_status_date);


--
-- Name: idx_dob_complaints_street; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_street ON public.dob_complaints USING btree (house_street);


--
-- Name: idx_dob_complaints_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_updated_at ON public.dob_complaints USING btree (updated_at);


--
-- Name: idx_dob_complaints_zip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_zip ON public.dob_complaints USING btree (zip_code);


--
-- Name: idx_dob_complaints_zip_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_complaints_zip_code ON public.dob_complaints USING btree (zip_code);


--
-- Name: idx_dob_permits_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_permits_bbl ON public.dob_permits USING btree (bbl);


--
-- Name: idx_dob_permits_filing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_permits_filing ON public.dob_permits USING btree (filing_date);


--
-- Name: idx_dob_violations_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_violations_bbl ON public.dob_violations USING btree (bbl);


--
-- Name: idx_dob_violations_issue; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_violations_issue ON public.dob_violations USING btree (issue_date);


--
-- Name: idx_dp_addr; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_addr ON public.dob_permits USING btree (upper(regexp_replace(((COALESCE(houseno, ''::text) || ' '::text) || COALESCE(street, ''::text)), '\s+'::text, ' '::text, 'g'::text)));


--
-- Name: idx_dp_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_bbl ON public.dob_permits USING btree (bbl);


--
-- Name: idx_dp_bbl_norm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_bbl_norm ON public.dob_permits USING btree (public.bbl_normalize(bbl));


--
-- Name: idx_dp_boro_block_lot; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_boro_block_lot ON public.dob_permits USING btree (upper(borough), ((NULLIF((raw ->> 'block'::text), ''::text))::integer), ((NULLIF((raw ->> 'lot'::text), ''::text))::integer));


--
-- Name: idx_dp_filed_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_filed_date ON public.dob_permits USING btree (filed_date);


--
-- Name: idx_dp_issuance_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_issuance_date ON public.dob_permits USING btree (issuance_date);


--
-- Name: idx_dp_job_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_job_number ON public.dob_permits USING btree (job_number);


--
-- Name: idx_dp_status_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dp_status_date ON public.dob_permits USING btree (status_date);


--
-- Name: idx_dv_addr; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_addr ON public.dob_violations USING btree (upper(regexp_replace(((COALESCE(houseno, ''::text) || ' '::text) || COALESCE(street, ''::text)), '\s+'::text, ' '::text, 'g'::text)));


--
-- Name: idx_dv_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_bbl ON public.dob_violations USING btree (bbl);


--
-- Name: idx_dv_bbl_norm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_bbl_norm ON public.dob_violations USING btree (public.bbl_normalize(bbl));


--
-- Name: idx_dv_boro_block_lot; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_boro_block_lot ON public.dob_violations USING btree (((NULLIF((raw ->> 'boro_code'::text), ''::text))::integer), ((NULLIF((raw ->> 'block'::text), ''::text))::integer), ((NULLIF((raw ->> 'lot'::text), ''::text))::integer));


--
-- Name: idx_dv_disp_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_disp_date ON public.dob_violations USING btree (disposition_date);


--
-- Name: idx_dv_issue_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_issue_date ON public.dob_violations USING btree (issue_date);


--
-- Name: idx_dv_violation_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_violation_number ON public.dob_violations USING btree (violation_number);


--
-- Name: idx_hpd_registrations_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hpd_registrations_bbl ON public.hpd_registrations USING btree (bbl);


--
-- Name: idx_hpd_violations_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hpd_violations_bbl ON public.hpd_violations USING btree (bbl);


--
-- Name: idx_mv_prop_events_dob_complaints_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_mv_prop_events_dob_complaints_bbl ON public.mv_property_events__dob_complaints USING btree (bbl);


--
-- Name: idx_pad_bin_bbl_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pad_bin_bbl_bbl ON public.pad_bin_bbl USING btree (bbl);


--
-- Name: idx_pluto_addr_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_addr_key ON public.pluto USING btree (upper(regexp_replace(((COALESCE(houseno, ''::text) || ' '::text) || COALESCE(street, ''::text)), '\s+'::text, ' '::text, 'g'::text)));


--
-- Name: idx_pluto_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_address ON public.pluto USING btree (street, houseno);


--
-- Name: idx_pluto_address_upper; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_address_upper ON public.pluto USING btree (upper(address));


--
-- Name: idx_pluto_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_bbl ON public.pluto USING btree (bbl);


--
-- Name: idx_pluto_bbl_norm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_bbl_norm ON public.pluto USING btree (public.bbl_normalize(bbl));


--
-- Name: idx_pluto_boro_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_boro_code ON public.pluto USING btree (public.borough_to_code(borough));


--
-- Name: idx_pluto_geom_wgs84; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_geom_wgs84 ON public.pluto USING gist (public.st_transform(public.st_setsrid(public.st_makepoint(longitude, latitude), 4326), 2263));


--
-- Name: idx_pluto_latlon; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_latlon ON public.pluto USING btree (latitude, longitude);


--
-- Name: idx_pluto_street_upper; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_street_upper ON public.pluto USING btree (upper(street));


--
-- Name: idx_pluto_zip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pluto_zip ON public.pluto USING btree (zipcode);


--
-- Name: idx_pv_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pv_bbl ON public.permits_violations USING btree (bbl);


--
-- Name: idx_stg_acris_legal_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_acris_legal_hash ON public.staging_acris_legal USING btree (row_hash);


--
-- Name: idx_stg_acris_master_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_acris_master_hash ON public.staging_acris_master USING btree (row_hash);


--
-- Name: idx_stg_acris_mtg_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_acris_mtg_hash ON public.staging_acris_mortgage USING btree (row_hash);


--
-- Name: idx_stg_dob_permits_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_dob_permits_hash ON public.staging_dob_permits USING btree (row_hash);


--
-- Name: idx_stg_dob_violations_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_dob_violations_hash ON public.staging_dob_violations USING btree (row_hash);


--
-- Name: idx_stg_hpd_reg_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_hpd_reg_hash ON public.staging_hpd_registrations USING btree (row_hash);


--
-- Name: idx_stg_hpd_violations_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_hpd_violations_hash ON public.staging_hpd_violations USING btree (row_hash);


--
-- Name: idx_stg_pluto_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stg_pluto_hash ON public.staging_pluto USING btree (row_hash);


--
-- Name: ix_addr_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_addr_trgm ON public.dim_address USING gin (full_norm public.gin_trgm_ops);


--
-- Name: ix_ingest_runs_recent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingest_runs_recent ON public.ingest_runs USING btree (source, version, started_at DESC);


--
-- Name: ix_mv_addr; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mv_addr ON public.property_search_base USING gin (address public.gin_trgm_ops);


--
-- Name: ix_mv_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mv_bbl ON public.property_search_base USING btree (bbl);


--
-- Name: ix_parcel_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parcel_bbl ON public.dim_parcel USING btree (bbl);


--
-- Name: ix_property_search_addr_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_property_search_addr_trgm ON public.property_search USING gin (address public.gin_trgm_ops);


--
-- Name: ux_dob_permits_job_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_dob_permits_job_number ON public.dob_permits USING btree (job_number) WHERE (job_number IS NOT NULL);


--
-- Name: ux_mv_permit_agg_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_permit_agg_bbl ON public.mv_permit_agg USING btree (bbl_norm);


--
-- Name: ux_permit_agg_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_permit_agg_bbl ON public.mv_permit_agg USING btree (bbl_norm);


--
-- Name: ux_property_rollup_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_property_rollup_bbl ON public.property_rollup USING btree (bbl);


--
-- Name: ux_property_search_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_property_search_bbl ON public.property_search_base USING btree (bbl);


--
-- Name: dim_parcel dim_parcel_addr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_parcel
    ADD CONSTRAINT dim_parcel_addr_id_fkey FOREIGN KEY (addr_id) REFERENCES public.dim_address(addr_id);


--
-- PostgreSQL database dump complete
--

\unrestrict Ode7sqBJWe6cMoFW607YWBbWC7dViGIzFrFnevgaHqmWHQIi2gfDIljvevYgqAg
