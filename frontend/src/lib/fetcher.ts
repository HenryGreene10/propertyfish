const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, '') ?? 'http://localhost:8000';

export type SearchParams = {
  limit?: number;
  offset?: number;
  year_min?: number;
  floors_min?: number;
  units_min?: number;
};

export async function searchFetcher([route, params]: [string, SearchParams]) {
  const qs = new URLSearchParams(
    Object.entries(params || {}).reduce((acc, [key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        acc[key] = String(value);
      }
      return acc;
    }, {} as Record<string, string>),
  ).toString();

  const res = await fetch(`${API_BASE}/${route}?${qs}`, { credentials: 'omit' });
  if (!res.ok) throw new Error(`Search failed ${res.status}`);
  return res.json();
}
