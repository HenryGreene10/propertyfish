// frontend/src/lib/types.ts
export type Serializable = string | number | boolean | null | undefined;

export type SearchFilters = {
  borough?: "MN" | "BK" | "QN" | "BX" | "SI";
  year_built_gte?: number;
  year_built_lte?: number;
  floors_eq?: number;
  units_gte?: number;
  limit?: number;
  offset?: number;
};

export type SearchCard = {
  bbl: string;
  address: string;
  borough: "MN" | "BK" | "QN" | "BX" | "SI";
  borough_full?: string | null;
  permit_count_12m?: number | null;
  last_permit_date?: string | null;
  // add fields later as backend grows
};

export type PropertyDetail = {
  bbl: string;
  address: string;
  borough: string;
  // expand later
};
