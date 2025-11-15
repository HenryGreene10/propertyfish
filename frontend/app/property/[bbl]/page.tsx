'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { PropertyDetail } from '@/lib/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

async function fetchPropertyDetail(bbl: string): Promise<PropertyDetail> {
  const res = await fetch(
    `${API_BASE_URL}/api/property/${encodeURIComponent(bbl)}/summary`,
    { cache: 'no-store' },
  );
  if (!res.ok) {
    throw new Error('Failed to load property detail');
  }
  return res.json();
}

function formatNumber(value?: number | null, suffix?: string) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—';
  }
  const base = value.toLocaleString();
  return suffix ? `${base} ${suffix}` : base;
}

function formatYear(value?: number | null) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—';
  }
  return String(Math.trunc(value));
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '—';
  }
  return parsed.toISOString().slice(0, 10);
}

type PropertyDetailPageProps = {
  params: { bbl: string };
};

export default function PropertyDetailPage({ params }: PropertyDetailPageProps) {
  const { bbl } = params;
  const [data, setData] = useState<PropertyDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError(null);
    setData(null);

    fetchPropertyDetail(bbl)
      .then((payload) => {
        if (!isMounted) return;
        setData(payload);
      })
      .catch((err) => {
        if (!isMounted) return;
        const message =
          err instanceof Error ? err.message : 'Unable to load property detail';
        setError(message);
      })
      .finally(() => {
        if (!isMounted) return;
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [bbl]);

  const permitInfo = useMemo(() => {
    if (!data) {
      return {
        count: null,
        date: null,
        description: null,
        hasData: false,
      };
    }
    const count =
      (typeof data.permit_count_12mo === 'number' && Number.isFinite(data.permit_count_12mo)
        ? data.permit_count_12mo
        : null) ??
      (typeof data.permit_count_12m === 'number' && Number.isFinite(data.permit_count_12m)
        ? data.permit_count_12m
        : null);
    const date = data.latest_permit_date ?? data.last_permit_date ?? null;
    const description =
      data.latest_permit_description ?? data.last_permit ?? null;
    const hasData = count !== null || !!date || !!description;
    return { count, date, description, hasData };
  }, [data]);

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <Link href="/search" className="inline-flex items-center text-sm text-blue-400 hover:text-blue-300">
        ← Back to search
      </Link>
      {isLoading && <div className="text-sm text-neutral-400">Loading property…</div>}
      {!isLoading && error && (
        <div className="text-sm text-red-500">Error: {error}</div>
      )}
      {!isLoading && !error && !data && (
        <div className="text-sm text-neutral-400">Property not found.</div>
      )}

      {data && (
        <>
          <section className="space-y-2">
            <h1 className="text-3xl font-semibold text-neutral-100">
              {data.address || 'Unknown property'}
            </h1>
            <div className="text-sm uppercase tracking-wide text-neutral-400">
              {data.borough_full ?? data.borough ?? '—'}
            </div>
            <div className="text-xs font-mono text-neutral-500">BBL {data.bbl}</div>
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Property Facts</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-1 gap-4 text-sm text-neutral-300">
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-neutral-500">
                      Year built
                    </dt>
                    <dd className="text-lg text-neutral-100">
                      {formatYear(data.yearbuilt ?? data.year_built)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-neutral-500">
                      Floors
                    </dt>
                    <dd className="text-lg text-neutral-100">
                      {formatNumber(data.numfloors ?? data.floors)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-neutral-500">
                      Units
                    </dt>
                    <dd className="text-lg text-neutral-100">
                      {formatNumber(data.unitstotal ?? data.units_total, 'total')} •{' '}
                      {formatNumber(data.unitsres, 'residential')}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-neutral-500">
                      Zoning
                    </dt>
                    <dd className="text-lg text-neutral-100">
                      {data.zonedist1 || '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-neutral-500">
                      Land use
                    </dt>
                    <dd className="text-lg text-neutral-100">
                      {data.landuse || '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-neutral-500">
                      Building area
                    </dt>
                    <dd className="text-lg text-neutral-100">
                      {formatNumber(data.bldgarea, 'sf')}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-neutral-500">
                      Lot area
                    </dt>
                    <dd className="text-lg text-neutral-100">
                      {formatNumber(data.lotarea, 'sf')}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Permits</CardTitle>
              </CardHeader>
              <CardContent>
                {!permitInfo.hasData && (
                  <div className="text-sm text-neutral-400">No recent permit data.</div>
                )}
                {permitInfo.hasData && (
                  <dl className="space-y-3 text-sm text-neutral-200">
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-neutral-500">
                        Permits (12 months)
                      </dt>
                      <dd className="text-lg text-neutral-100">
                        {permitInfo.count === null
                          ? '—'
                          : permitInfo.count.toLocaleString()}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-neutral-500">
                        Latest permit date
                      </dt>
                      <dd className="text-lg text-neutral-100">
                        {formatDate(permitInfo.date)}
                      </dd>
                    </div>
                    {permitInfo.description && (
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-neutral-500">
                          Description
                        </dt>
                        <dd className="text-sm text-neutral-200">
                          {permitInfo.description}
                        </dd>
                      </div>
                    )}
                  </dl>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
