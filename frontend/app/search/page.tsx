'use client';

import { useState } from 'react';

import FiltersPanel from '@/components/FiltersPanel';
import PropertyCard from '@/components/PropertyCard';
import type { SearchCard, SearchFilters } from '@/lib/types';

type SearchItem = {
  bbl: string;
  address: string;
  borough: string;
  borough_full?: string | null;
  zipcode?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  year_built?: number | null;
  floors?: number | null;
  units_total?: number | null;
  permit_count_12m?: number | null;
  last_permit_date?: string | null;
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
    ['permits_min_12m', asNumber(filters.permits_min_12m)],
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

function mapToCard(item: SearchItem): SearchCard {
  return {
    bbl: item.bbl,
    address: item.address,
    borough: item.borough as SearchCard['borough'],
    borough_full: item.borough_full,
    year_built: item.year_built,
    floors: item.floors,
    units_total: item.units_total,
    permit_count_12m: item.permit_count_12m,
    last_permit_date: item.last_permit_date,
  };
}

export default function SearchPage() {
  const [results, setResults] = useState<SearchCard[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleApply = async (nextFilters: Partial<SearchFilters>) => {
    setHasSearched(true);
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
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Unable to fetch search results';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="mb-4 text-2xl font-bold">Search</h1>
      <FiltersPanel onApply={handleApply} />
      {!hasSearched && (
        <div className="py-6 text-center text-sm text-neutral-500">
          Enter filters and click Apply to see results.
        </div>
      )}
      {hasSearched && isLoading && (
        <div className="text-sm text-neutral-400">Loading…</div>
      )}
      {hasSearched && error && !isLoading && (
        <div className="text-sm text-red-500">Error: {error}</div>
      )}
      {hasSearched && !isLoading && !error && results.length === 0 && (
        <div className="text-sm text-neutral-400">No results.</div>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {results.map((item) => (
          <PropertyCard key={item.bbl} p={item} />
        ))}
      </div>
    </div>
  );
}
