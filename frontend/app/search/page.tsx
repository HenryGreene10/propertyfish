'use client';

import React from 'react';
import useSWR from 'swr';

import { FiltersPanel } from '@/components/FiltersPanel';
import { PropertyCard } from '@/components/PropertyCard';
import { getSearch } from '@/lib/api';
import type { SearchFilters } from '@/lib/types';

type Ui = {
  borough?: string;
  year_built?: string;
  num_floors?: string;
  units_gte?: string;
};

const BLANK: Ui = {
  borough: '',
  year_built: '',
  num_floors: '',
  units_gte: '',
};

const normalize = (filters: Ui): Partial<SearchFilters> => {
  const normalized: Partial<SearchFilters> = {
    limit: 20,
    offset: 0,
  };

  const borough = filters.borough?.trim();
  if (borough) {
    normalized.borough = borough as SearchFilters['borough'];
  }

  const year = parseInt(filters.year_built ?? '', 10);
  if (!Number.isNaN(year)) {
    normalized.year_built_gte = year;
    normalized.year_built_lte = year;
  }

  const floors = parseInt(filters.num_floors ?? '', 10);
  if (!Number.isNaN(floors)) {
    normalized.num_floors_gte = floors;
    normalized.num_floors_lte = floors;
  }

  const units = parseInt(filters.units_gte ?? '', 10);
  if (!Number.isNaN(units)) {
    normalized.units_gte = units;
  }

  return normalized;
};

const DEFAULT_FILTERS = normalize(BLANK);

export default function SearchPage() {
  const [ui, setUi] = React.useState<Ui>(() => ({ ...BLANK }));
  const [appliedUi, setAppliedUi] = React.useState<Ui | null>(null);
  const [filters, setFilters] = React.useState<Partial<SearchFilters>>(DEFAULT_FILTERS);
  const filtersRef = React.useRef<Partial<SearchFilters>>(filters);

  React.useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  const handleUiChange = React.useCallback((next: Ui) => {
    const sanitized: Ui = {
      borough: next.borough ?? '',
      year_built: next.year_built ?? '',
      num_floors: next.num_floors ?? '',
      units_gte: next.units_gte ?? '',
    };

    setUi(sanitized);
  }, []);

  const key = React.useMemo(
    () => ['search', JSON.stringify(filters)] as const,
    [filters],
  );
  console.debug('[SWR] key =', key);

  const { data, error, isValidating, mutate } = useSWR(
    key,
    () => getSearch(filtersRef.current),
    {
      revalidateOnFocus: false,
      revalidateOnMount: false,
    },
  );

  const onApply = React.useCallback(() => {
    const snapshot: Ui = {
      borough: ui.borough ?? '',
      year_built: ui.year_built ?? '',
      num_floors: ui.num_floors ?? '',
      units_gte: ui.units_gte ?? '',
    };

    const nextFilters = normalize(snapshot);
    filtersRef.current = nextFilters;
    setFilters(nextFilters);
    setAppliedUi(snapshot);

    console.debug('[UI] Apply pressed → mutate', nextFilters);
    mutate();
  }, [mutate, ui.borough, ui.num_floors, ui.units_gte, ui.year_built]);

  const summaryParts: string[] = [];
  if (appliedUi?.borough) summaryParts.push(`borough=${appliedUi.borough}`);
  if (appliedUi?.year_built) summaryParts.push(`year=${appliedUi.year_built}`);
  if (appliedUi?.num_floors) summaryParts.push(`floors=${appliedUi.num_floors}`);
  if (appliedUi?.units_gte) summaryParts.push(`units≥${appliedUi.units_gte}`);
  const summary = summaryParts.join(' ');

  const results = data?.results ?? [];
  const totalCount = data?.total ?? data?.results?.length ?? 0;
  const hasApplied = Boolean(appliedUi);
  const showLoading = hasApplied && isValidating;
  const highlightYear = Boolean(appliedUi?.year_built);

  return (
    <div className="container" style={{ paddingBlock: '32px' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 600, marginBottom: '24px' }}>Search</h1>

      <FiltersPanel value={ui} onChange={handleUiChange} onApply={onApply} />

      {!hasApplied && (
        <p className="muted" style={{ marginBottom: '12px' }}>
          Set filters and press Apply.
        </p>
      )}

      {hasApplied && summary && (
        <div className="muted" style={{ fontSize: '12px', marginBottom: '12px' }}>
          {summary}
        </div>
      )}

      {hasApplied && error && !isValidating && (
        <p className="muted" style={{ marginBottom: '12px' }}>
          API error.
        </p>
      )}

      {hasApplied && !error && showLoading && <p>Loading...</p>}

      {hasApplied &&
        !error &&
        !isValidating &&
        (data?.total ?? data?.results?.length ?? 0) === 0 && <p>No results.</p>}

      {hasApplied && !error && !showLoading && totalCount > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {results.map((item) => (
            <PropertyCard key={item.bbl} item={item} highlightYear={highlightYear} />
          ))}
        </div>
      )}
    </div>
  );
}
