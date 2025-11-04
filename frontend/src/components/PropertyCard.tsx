'use client';

import React from 'react';
import { useRouter } from 'next/navigation';

import type { SearchCard } from '@/lib/types';

type PropertyCardProps = {
  item: SearchCard;
  highlightYear?: boolean;
};

export function PropertyCard({ item, highlightYear = false }: PropertyCardProps) {
  const router = useRouter();

  const handleNavigate = React.useCallback(() => {
    if (!item?.bbl) return;
    router.push(`/property/${item.bbl}`);
  }, [item?.bbl, router]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleNavigate();
    }
  };

  const yearBuilt = item.year_built ?? '—';
  const units = item.units_total ?? item.units_residential ?? '—';
  const landUse = item.land_use_desc ?? item.land_use_code ?? item.land_use ?? '—';

  return (
    <div
      role="button"
      tabIndex={0}
      className="card p-4 mb-4 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
      onClick={handleNavigate}
      onKeyDown={handleKeyDown}
    >
      <div className="text-lg font-semibold">
        {item.address}{' '}
        <span className="muted">· {item.borough ?? '—'}</span>
      </div>

      <div className="muted text-sm mt-1">
        {highlightYear ? <strong>Year built: {yearBuilt}</strong> : <>Year built: {yearBuilt}</>}
        {' · '}Units: {units} · Land use: {landUse}
      </div>

      <div className="flex gap-2 flex-wrap mt-3 text-xs muted">
        {typeof item.permit_count_12m === 'number' && (
          <span className="px-2 py-1 rounded border border-neutral-700">
            Permits (12m): {item.permit_count_12m}
          </span>
        )}
        {typeof item.last_sale_price === 'number' && (
          <span className="px-2 py-1 rounded border border-neutral-700">
            Last sale: ${item.last_sale_price.toLocaleString()}
          </span>
        )}
      </div>
    </div>
  );
}

export type { PropertyCardProps };
