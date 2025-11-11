// frontend/src/lib/types.ts
export type Serializable = string | number | boolean | null | undefined;

export type SearchFilters = {
  q?: string;
  borough?: "MN" | "BK" | "QN" | "BX" | "SI";
  limit?: number;
  offset?: number;
  year_min?: number;
  floors_min?: number;
  units_min?: number;
  permits_min_12m?: number;
  sort?: "last_permit_date" | "year_built" | "permit_count_12m" | "relevance";
  order?: "asc" | "desc";
};

export type SearchCard = {
  bbl: string;
  address: string;
  borough: "MN" | "BK" | "QN" | "BX" | "SI";
  borough_full?: string | null;
  year_built?: number | null;
  floors?: number | null;
  units_total?: number | null;
  permit_count_12m?: number | null;
  last_permit?: string | null;
  last_permit_date?: string | null;
  // add fields later as backend grows
};

export type PropertyDetail = {
  bbl: string;
  address: string;
  borough: string;
  // expand later
};
