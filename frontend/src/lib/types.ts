// frontend/src/lib/types.ts
export type Serializable = string | number | boolean | null | undefined;

export type SearchFilters = {
  q?: string;
  borough?: 'MN' | 'BK' | 'QN' | 'BX' | 'SI';
  limit?: number;
  offset?: number;
  year_min?: number;
  floors_min?: number;
  units_min?: number;
  permits_min_12m?: number;
  sort?: 'last_permit_date' | 'year_built' | 'permit_count_12m' | 'relevance';
  order?: 'asc' | 'desc';
};

export interface PropertySummary {
  bbl: string;
  borough: string;
  address: string;
  borough_full?: string | null;
  zipcode?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  yearbuilt?: number | null;
  numfloors?: number | null;
  unitsres?: number | null;
  unitstotal?: number | null;
  stories?: number | null;
  lot_sqft?: number | null;
  building_dimensions?: string | null;
  lot_dimensions?: string | null;
  zoning?: string | null;
  zonedist1?: string | null;
  landuse?: string | null;
  bldgarea?: number | null;
  lotarea?: number | null;
  permit_count_12mo?: number | null;
  latest_permit_date?: string | null;
  latest_permit_description?: string | null;
  year_built?: number | null;
  floors?: number | null;
  units_total?: number | null;
  permit_count_12m?: number | null;
  last_permit?: string | null;
  last_permit_date?: string | null;
  last_sale_date?: string | null;
  last_sale_price?: number | null;
  tax_year?: number | null;
  market_value?: number | null;
  tax_amount?: number | null;
}

export type PropertyDetail = PropertySummary & {
  last_sale_date?: string | null;
  last_sale_price?: number | null;
  tax_year?: number | null;
  market_value?: number | null;
  tax_amount?: number | null;
  [key: string]: Serializable;
};
