export type SearchFilters = {
  q?: string;
  borough?: 'BK' | 'QN' | 'MN' | 'BX' | 'SI';
  year_built_gte?: number;
  year_built_lte?: number;
  num_floors_gte?: number;
  num_floors_lte?: number;
  units_gte?: number;
  units_lte?: number;
  has_permits_12m?: boolean;
  has_complaints_12m?: boolean;
  last_sale_date_gte?: string;
  last_sale_date_lte?: string;
  limit?: number;
  offset?: number;
};

export type SearchCard = {
  bbl: string;
  address: string;
  borough: string;
  year_built?: number;
  units_residential?: number;
  units_total?: number;
  land_use?: string;
  land_use_code?: string;
  land_use_desc?: string;
  permit_count_12m?: number;
  last_permit_date?: string;
  complaints_12m?: number;
  last_complaint_date?: string;
  last_sale_date?: string;
  last_sale_price?: number;
};

export type PermitRow = {
  job_number: string;
  status?: string;
  issuance_date?: string;
  filing_date?: string;
};

export type PropertyDetail = {
  bbl: string;
  address: string;
  borough: string;
  pluto: {
    year_built?: number;
    units_residential?: number;
    land_use?: string;
    centroid?: { lat: number; lng: number };
    bbox?: [number, number, number, number];
  };
  agg: {
    permit_count_12m?: number;
    last_permit_date?: string;
    complaints_12m?: number;
    last_complaint_date?: string;
  };
  recent_permits: PermitRow[];
  acris?: {
    last_sale_date?: string | null;
    last_sale_price?: number | null;
    owners?: string[];
    sales_history?: any[];
  };
};
