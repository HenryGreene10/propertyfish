'use client';

import { FormEvent, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import type { SearchFilters } from '@/lib/types';

type FiltersPanelProps = {
  onApply: (p: Partial<SearchFilters>) => void;
};

export default function FiltersPanel({ onApply }: FiltersPanelProps) {
  const [query, setQuery] = useState('');
  const [borough, setBorough] = useState('');
  const [yearMin, setYearMin] = useState<number | ''>('');
  const [permitsMin, setPermitsMin] = useState<number | ''>('');

  const handleApply = () => {
    onApply({
      q: query.trim() === '' ? undefined : query.trim(),
      borough: borough === '' ? undefined : (borough as SearchFilters['borough']),
      limit: 20,
      offset: 0,
      year_min: yearMin === '' ? undefined : yearMin,
      permits_min_12m: permitsMin === '' ? undefined : permitsMin,
    });
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    handleApply();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mb-6 rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 shadow-sm"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-4 lg:items-end">
        <div className="flex flex-col gap-1 lg:col-span-2">
          <label className="text-xs uppercase tracking-wide text-neutral-500">
            Search
          </label>
          <Input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Address or BBL"
            className="sm:w-full"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-neutral-500">
            Borough
          </label>
          <select
            value={borough}
            onChange={(e) => setBorough(e.target.value)}
            className="rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="MN">Manhattan</option>
            <option value="BX">Bronx</option>
            <option value="BK">Brooklyn</option>
            <option value="QN">Queens</option>
            <option value="SI">Staten Island</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-neutral-500">Year ≥</label>
          <Input
            type="number"
            inputMode="numeric"
            value={yearMin}
            onChange={(e) =>
              setYearMin(e.target.value === '' ? '' : Number(e.target.value))
            }
            placeholder="e.g. 1920"
            className="sm:w-full"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-neutral-500">
            Permits (12m) ≥
          </label>
          <Input
            type="number"
            inputMode="numeric"
            value={permitsMin}
            onChange={(e) =>
              setPermitsMin(e.target.value === '' ? '' : Number(e.target.value))
            }
          />
        </div>
        <div className="flex items-end">
          <Button className="w-full sm:w-auto" type="submit">
            Apply
          </Button>
        </div>
      </div>
    </form>
  );
}
