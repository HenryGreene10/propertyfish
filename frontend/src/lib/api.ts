import { API } from './config';
import type { PropertyDetail, PropertySummary, SearchFilters } from './types';

type Serializable = string | number | boolean | null | undefined;
type QueryObject = Partial<
  Record<keyof SearchFilters, Serializable | Serializable[]>
>;

export function toQS(obj: QueryObject): string {
  const params = new URLSearchParams();

  Object.entries(obj).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (entry === undefined || entry === null) return;
        params.append(key, String(entry));
      });
      return;
    }
    params.append(key, String(value));
  });

  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function getSearch(
  filters: Partial<SearchFilters>,
): Promise<{ results: PropertySummary[]; total: number }> {
  const query = toQS(filters);
  const url = `${API}/search${query}`;
  console.debug('[API] getSearch →', url);

  const res = await fetch(url, { cache: 'no-store' });

  // TEMP: one-shot debug so we can see what's happening
  console.debug('search fetch', {
    url,
    status: res.status,
    ok: res.ok,
    ct: res.headers.get('content-type'),
  });

  // treat 200, 204, 404 all as "not an exception" (just empty results)
  if (res.status >= 500) {
    throw new Error(`Request failed with status ${res.status}`);
  }

  const raw = await res.json().catch(() => ({} as unknown));
  const payload = Array.isArray(raw)
    ? { results: raw }
    : raw && typeof raw === 'object'
      ? (raw as Record<string, unknown>)
      : {};

  const resultSource =
    (payload as any).results ?? (payload as any).items ?? [];
  const results = Array.isArray(resultSource)
    ? (resultSource as PropertySummary[])
    : [];

  const totalCandidate =
    (payload as any).total ?? (payload as any).count ?? results.length;
  const total =
    typeof totalCandidate === 'number' ? totalCandidate : results.length;

  return { results, total };
}

export async function getProperty(bbl: string): Promise<PropertyDetail> {
  const res = await fetch(`${API}/property/${bbl}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as PropertyDetail;
}
