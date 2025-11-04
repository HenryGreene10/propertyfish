'use client';
import { useMemo, useState } from 'react';
import useSWR from 'swr';

import FiltersPanel from '@/components/FiltersPanel';
import PropertyCard from '@/components/PropertyCard';
import { searchFetcher, type SearchParams } from '@/lib/fetcher';

export default function SearchPage() {
  const [params, setParams] = useState<SearchParams>({ limit: 20, offset: 0 });

  const key = useMemo(() => ['search', params] as const, [JSON.stringify(params)]);
  const { data, error, isLoading } = useSWR(key, searchFetcher);

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Search</h1>
      <FiltersPanel onApply={(p) => setParams(p)} />
      {isLoading && <div className="text-sm">Loading…</div>}
      {error && (
        <div className="text-sm text-red-600">
          Error: {String((error as Error).message ?? error)}
        </div>
      )}
      {!isLoading && data?.items?.length === 0 && <div className="text-sm">No results.</div>}
      <div className="grid md:grid-cols-2 gap-4">
        {data?.items?.map((p: any) => (
          <PropertyCard key={p.bbl ?? Math.random()} p={p} />
        ))}
      </div>
    </div>
  );
}
