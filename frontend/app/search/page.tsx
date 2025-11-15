'use client';

import { FormEvent, useState } from 'react';

import PropertyCard from '@/components/PropertyCard';
import type { PropertySummary, SearchFilters } from '@/lib/types';

type SearchItem = {
  bbl: string;
  address: string;
  borough: string;
  borough_full?: string | null;
  zipcode?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  yearbuilt?: number | null;
  year_built?: number | null;
  numfloors?: number | null;
  floors?: number | null;
  unitsres?: number | null;
  unitstotal?: number | null;
  units_total?: number | null;
  zonedist1?: string | null;
  landuse?: string | null;
  bldgarea?: number | null;
  lotarea?: number | null;
  permit_count_12mo?: number | null;
  permit_count_12m?: number | null;
  latest_permit_date?: string | null;
  last_permit_date?: string | null;
  latest_permit_description?: string | null;
  last_permit?: string | null;
};

type SearchResponse = {
  total: number;
  items: SearchItem[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

const SORT_WHITELIST: ReadonlySet<NonNullable<SearchFilters['sort']>> = new Set([
  'last_permit_date',
  'year_built',
  'permit_count_12m',
  'relevance',
]);
const ORDER_WHITELIST: ReadonlySet<'asc' | 'desc'> = new Set(['asc', 'desc']);

function clampLimit(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return undefined;
  return Math.min(Math.max(Math.trunc(value), 1), 50);
}

function normalizeOffset(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return undefined;
  return Math.max(0, Math.trunc(value));
}

function asNumber(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return undefined;
  return value;
}

function buildSearchParams(filters: Partial<SearchFilters> = {}) {
  const params = new URLSearchParams();

  const text = typeof filters.q === 'string' ? filters.q.trim() : '';
  if (text) {
    params.set('q', text);
  }
  if (filters.borough) {
    params.set('borough', filters.borough);
  }

  const numericEntries: Array<[keyof SearchFilters, number | undefined]> = [
    ['limit', clampLimit(filters.limit)],
    ['offset', normalizeOffset(filters.offset)],
    ['year_min', asNumber(filters.year_min)],
  ];
  numericEntries.forEach(([key, value]) => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      params.set(key, String(value));
    }
  });

  if (filters.sort && SORT_WHITELIST.has(filters.sort)) {
    params.set('sort', filters.sort);
  }
  if (filters.order && ORDER_WHITELIST.has(filters.order)) {
    params.set('order', filters.order);
  }

  return params;
}

function toSearchResponse(payload: unknown): SearchResponse {
  const raw = (payload ?? {}) as {
    total?: number;
    items?: SearchItem[];
    rows?: SearchItem[];
  };

  const items = Array.isArray(raw.items)
    ? raw.items
    : Array.isArray(raw.rows)
      ? raw.rows
      : [];
  const total =
    typeof raw.total === 'number' && Number.isFinite(raw.total)
      ? raw.total
      : items.length;

  return { total, items };
}

function preferNumber(...values: Array<number | null | undefined>) {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

function preferString(...values: Array<string | null | undefined>) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim() !== '') {
      return value;
    }
  }
  return null;
}

function mapToCard(item: SearchItem): PropertySummary {
  return {
    bbl: item.bbl,
    address: item.address,
    borough: item.borough,
    borough_full: item.borough_full,
    zipcode: item.zipcode,
    latitude: item.latitude,
    longitude: item.longitude,
    yearbuilt: preferNumber(item.yearbuilt, item.year_built),
    year_built: item.year_built,
    numfloors: preferNumber(item.numfloors, item.floors),
    floors: item.floors,
    unitsres: item.unitsres,
    unitstotal: preferNumber(item.unitstotal, item.units_total),
    units_total: item.units_total,
    zonedist1: item.zonedist1,
    landuse: item.landuse,
    bldgarea: item.bldgarea,
    lotarea: item.lotarea,
    permit_count_12mo: preferNumber(item.permit_count_12mo, item.permit_count_12m),
    permit_count_12m: item.permit_count_12m,
    latest_permit_date: preferString(item.latest_permit_date, item.last_permit_date),
    last_permit_date: item.last_permit_date,
    latest_permit_description: preferString(
      item.latest_permit_description,
      item.last_permit,
    ),
    last_permit: item.last_permit,
  };
}

export default function SearchPage() {
  const [results, setResults] = useState<PropertySummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [query, setQuery] = useState('');
  const [boroughFilter, setBoroughFilter] = useState('');
  const [yearMin, setYearMin] = useState<number | ''>('');

  const handleApply = async (nextFilters: Partial<SearchFilters>) => {
    setIsLoading(true);
    setError(null);
    setResults([]);

    const params = buildSearchParams(nextFilters);
    const qs = params.toString();
    const url = `${API_BASE}/api/search${qs ? `?${qs}` : ''}`;
    console.debug('PF-FE-SEARCH', url);

    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }
      const data = toSearchResponse(await res.json());
      setResults(data.items.map(mapToCard));
      setHasSearched(true);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Unable to fetch search results';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    handleApply({
      q: query.trim() === '' ? undefined : query.trim(),
      borough: boroughFilter === '' ? undefined : (boroughFilter as SearchFilters['borough']),
      limit: 20,
      offset: 0,
      year_min: yearMin === '' ? undefined : yearMin,
    });
  };

  const fieldClasses =
    'w-full rounded-lg border border-charcoal_brown-600 bg-carbon_black-300 px-3 py-2 text-sm text-floral_white placeholder:text-dust_grey-500 focus:border-spicy_paprika-500 focus:ring-2 focus:ring-spicy_paprika-500 focus:outline-none transition';

  return (
    <div className="min-h-screen bg-carbon_black text-floral_white-500">
      <div className="mx-auto max-w-5xl p-6">
        <h1 className="mb-4 text-2xl font-bold text-floral_white-500">Search</h1>
        <form
          onSubmit={handleSubmit}
          className="mb-6 rounded-xl border border-charcoal_brown-600 bg-charcoal_brown-400 p-4 shadow-sm"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-4 lg:items-end">
            <div className="flex flex-col gap-2 lg:col-span-2">
              <label className="text-xs uppercase tracking-wide text-dust_grey-500">
                Search
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Address or BBL"
                className={fieldClasses}
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-wide text-dust_grey-500">
                Borough
              </label>
              <select
                value={boroughFilter}
                onChange={(e) => setBoroughFilter(e.target.value)}
                className={fieldClasses}
              >
                <option value="">Any</option>
                <option value="MN">Manhattan</option>
                <option value="BX">Bronx</option>
                <option value="BK">Brooklyn</option>
                <option value="QN">Queens</option>
                <option value="SI">Staten Island</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-wide text-dust_grey-500">
                Year ≥
              </label>
              <input
                type="number"
                inputMode="numeric"
                value={yearMin}
                onChange={(e) =>
                  setYearMin(e.target.value === '' ? '' : Number(e.target.value))
                }
                placeholder="e.g. 1920"
                className={fieldClasses}
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-lg px-6 py-2 font-medium text-floral_white-500 shadow-sm transition-colors duration-150 sm:w-auto bg-spicy_paprika-500 hover:bg-spicy_paprika-400 disabled:cursor-not-allowed disabled:bg-spicy_paprika-300"
              >
                {isLoading ? 'Searching…' : 'Apply'}
              </button>
            </div>
          </div>
        </form>
        {!hasSearched && !isLoading && (
          <div className="py-6 text-center text-sm text-dust_grey-500">
            Enter filters and click Apply to see results.
          </div>
        )}
        {isLoading && (
          <div className="text-sm text-dust_grey-400">Loading…</div>
        )}
        {error && !isLoading && (
          <div className="text-sm text-spicy_paprika-500">Error: {error}</div>
        )}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {results.map((item) => (
            <PropertyCard key={item.bbl} p={item} />
          ))}
        </div>
        {!isLoading && hasSearched && !error && results.length === 0 && (
          <p className="mt-8 text-sm text-dust_grey-500">
            No properties found. Try broadening your search (for example, just "82nd street" or
            removing the year filter).
          </p>
        )}
      </div>
    </div>
  );
}
