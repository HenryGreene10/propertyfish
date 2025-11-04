'use client';
import { useMemo, useState } from 'react';
import useSWR from 'swr';

import FiltersPanel from '@/components/FiltersPanel';
import PropertyCard from '@/components/PropertyCard';
import { getSearch } from '@/lib/api';
import type { SearchFilters } from '@/lib/types';

export default function SearchPage() {
  const [filters, setFilters] = useState<Partial<SearchFilters>>({
    limit: 20,
    offset: 0,
  });

  const key = useMemo(() => ['search', filters] as const, [filters]);
  const { data, error, isValidating } = useSWR(key, ([, currentFilters]) =>
    getSearch(currentFilters),
  );

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="mb-4 text-2xl font-bold">Search</h1>
      <FiltersPanel onApply={(p) => setFilters(p)} />
      {isValidating && <div className="text-sm text-neutral-400">Loading…</div>}
      {error && !isValidating && (
        <div className="text-sm text-red-500">
          Error: {String((error as Error).message ?? error)}
        </div>
      )}
      {!error && !isValidating && (data?.results?.length ?? 0) === 0 && (
        <div className="text-sm text-neutral-400">No results.</div>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {data?.results?.map((p) => (
          <PropertyCard key={p.bbl} p={p} />
        ))}
      </div>
    </div>
  );
}
