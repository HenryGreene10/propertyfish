// frontend/src/lib/types.ts
export type Serializable = string | number | boolean | null | undefined;

export type SearchFilters = {
  borough?: "MN" | "BK" | "QN" | "BX" | "SI";
  limit?: number;
  offset?: number;
  year_min?: number;
  floors_min?: number;
  units_min?: number;
};

export type SearchCard = {
  bbl: string;
  address: string;
  borough: "MN" | "BK" | "QN" | "BX" | "SI";
  borough_full?: string | null;
  year_built?: number | null;
  floors?: number | null;
  units_total?: number | null;
  permits_last_12m?: number | null;
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
