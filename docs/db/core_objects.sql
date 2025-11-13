--
-- PostgreSQL database dump
--

\restrict gWQm83vxbcwseXLkmyJusAYMHZU3rGop7f2aXXUEacsq21TpoIey5UoSrSeQFZQ

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

SET default_tablespace = '';

SET default_table_access_method = heap;

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
-- Name: dob_permits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_permits ALTER COLUMN id SET DEFAULT nextval('public.dob_permits_id_seq'::regclass);


--
-- Name: pluto id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pluto ALTER COLUMN id SET DEFAULT nextval('public.pluto_id_seq'::regclass);


--
-- Name: dob_permits dob_permits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_permits
    ADD CONSTRAINT dob_permits_pkey PRIMARY KEY (id);


--
-- Name: pluto pluto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pluto
    ADD CONSTRAINT pluto_pkey PRIMARY KEY (id);


--
-- Name: dob_permits uq_dob_permits_job_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dob_permits
    ADD CONSTRAINT uq_dob_permits_job_number UNIQUE (job_number);


--
-- Name: idx_dob_permits_bbl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_permits_bbl ON public.dob_permits USING btree (bbl);


--
-- Name: idx_dob_permits_filing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dob_permits_filing ON public.dob_permits USING btree (filing_date);


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
-- Name: ix_property_search_addr_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_property_search_addr_trgm ON public.property_search USING gin (address public.gin_trgm_ops);


--
-- Name: ux_dob_permits_job_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_dob_permits_job_number ON public.dob_permits USING btree (job_number) WHERE (job_number IS NOT NULL);


--
-- PostgreSQL database dump complete
--

\unrestrict gWQm83vxbcwseXLkmyJusAYMHZU3rGop7f2aXXUEacsq21TpoIey5UoSrSeQFZQ
