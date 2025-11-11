const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, '') ?? 'http://localhost:8000';

export type SearchParams = {
  q?: string;
  borough?: string;
  limit?: number;
  offset?: number;
  year_min?: number;
  floors_min?: number;
  units_min?: number;
  permits_min_12m?: number;
  sort?: "last_permit_date" | "year_built" | "permit_count_12m" | "relevance";
  order?: "asc" | "desc";
};

const NUMERIC_KEYS = new Set([
  "limit",
  "offset",
  "year_min",
  "permits_min_12m",
]);

export async function searchFetcher([route, params]: [string, SearchParams]) {
  const filtered = Object.entries(params || {}).reduce(
    (acc, [key, value]) => {
      if (value === undefined || value === null || value === '') {
        return acc;
      }
      if (NUMERIC_KEYS.has(key)) {
        const num = Number(value);
        if (!Number.isFinite(num)) {
          return acc;
        }
        acc[key] = String(num);
        return acc;
      }
      acc[key] = String(value);
      return acc;
    },
    {} as Record<string, string>,
  );
  const qs = new URLSearchParams(filtered).toString();

  const res = await fetch(`${API_BASE}/${route}?${qs}`, { credentials: 'omit' });
  if (!res.ok) throw new Error(`Search failed ${res.status}`);
  return res.json();
}
