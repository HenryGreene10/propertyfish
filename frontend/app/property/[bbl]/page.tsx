'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

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
  const router = useRouter();
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

  const hasAddress = !!(data && data.address && data.address.trim() !== '');
  const encodedAddress = hasAddress ? encodeURIComponent(`${data?.address}, New York, NY`) : null;
  const mapsEmbedUrl = encodedAddress
    ? `https://www.google.com/maps?q=${encodedAddress}&output=embed`
    : null;
  const mapsViewUrl = encodedAddress
    ? `https://www.google.com/maps/search/?api=1&query=${encodedAddress}`
    : null;

  return (
    <div className="min-h-screen bg-carbon_black text-floral_white-500">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <button
          type="button"
          onClick={() => router.back()}
          className="inline-flex items-center text-sm text-spicy_paprika-500 hover:text-spicy_paprika-400"
        >
          ← Back to search
        </button>
        {isLoading && <div className="text-sm text-dust_grey-400">Loading property…</div>}
        {!isLoading && error && (
          <div className="text-sm text-spicy_paprika-500">Error: {error}</div>
        )}
        {!isLoading && !error && !data && (
          <div className="text-sm text-dust_grey-400">Property not found.</div>
        )}

        {data && (
          <>
            <section className="space-y-2">
              <h1 className="text-3xl font-semibold text-floral_white-500">
                {data.address || 'Unknown property'}
              </h1>
              <div className="text-sm uppercase tracking-wide text-dust_grey-500">
                {data.borough_full ?? data.borough ?? '—'}
              </div>
              <div className="text-xs font-mono text-dust_grey-500">BBL {data.bbl}</div>
            </section>

            <div className="mt-6 mb-8 flex h-56 w-full items-center justify-center rounded-xl border border-neutral-800 bg-neutral-900/80 text-xs uppercase tracking-wide text-neutral-500">
              Property photo coming soon
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card className="!border-charcoal_brown-600 !bg-charcoal_brown-400">
                <CardHeader>
                  <CardTitle className="!text-floral_white-500">Property Facts</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="grid grid-cols-1 gap-4 text-sm text-floral_white-500">
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                        Year built
                      </dt>
                      <dd className="text-lg text-floral_white-500">
                        {formatYear(data.yearbuilt ?? data.year_built)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                        Floors
                      </dt>
                      <dd className="text-lg text-floral_white-500">
                        {formatNumber(data.numfloors ?? data.floors)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                        Units
                      </dt>
                      <dd className="text-lg text-floral_white-500">
                        {formatNumber(data.unitstotal ?? data.units_total, 'total')} •{' '}
                        {formatNumber(data.unitsres, 'residential')}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                        Zoning
                      </dt>
                      <dd className="text-lg text-floral_white-500">
                        {data.zoning ?? data.zonedist1 ?? '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                        Land use
                      </dt>
                      <dd className="text-lg text-floral_white-500">
                        {data.landuse || '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                        Building area
                      </dt>
                      <dd className="text-lg text-floral_white-500">
                        {formatNumber(data.bldgarea, 'sf')}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                        Lot area
                      </dt>
                      <dd className="text-lg text-floral_white-500">
                        {formatNumber(data.lotarea, 'sf')}
                      </dd>
                    </div>
                  </dl>
                  <div className="mt-8 space-y-1">
                    <div className="font-semibold text-sm tracking-wide text-dust_grey-300">
                      Sales &amp; Taxes
                    </div>
                    <div className="text-sm text-dust_grey-200">
                      Last sale date: {data.last_sale_date ?? '—'}
                    </div>
                    <div className="text-sm text-dust_grey-200">
                      Last sale price:{' '}
                      {data.last_sale_price != null
                        ? `$${data.last_sale_price.toLocaleString()}`
                        : '—'}
                    </div>
                    <div className="text-sm text-dust_grey-200">
                      Tax year: {data.tax_year ?? '—'}
                    </div>
                    <div className="text-sm text-dust_grey-200">
                      Market value:{' '}
                      {data.market_value != null
                        ? `$${data.market_value.toLocaleString()}`
                        : '—'}
                    </div>
                    <div className="text-sm text-dust_grey-200">
                      Tax amount:{' '}
                      {data.tax_amount != null
                        ? `$${data.tax_amount.toLocaleString()}`
                        : '—'}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="!border-charcoal_brown-600 !bg-charcoal_brown-400">
                <CardHeader>
                  <CardTitle className="!text-floral_white-500">Permits</CardTitle>
                </CardHeader>
                <CardContent>
                  {!permitInfo.hasData && (
                    <div className="text-sm text-dust_grey-400">No recent permit data.</div>
                  )}
                  {permitInfo.hasData && (
                    <dl className="space-y-3 text-sm text-floral_white-500">
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                          Permits (12 months)
                        </dt>
                        <dd className="text-lg text-floral_white-500">
                          {permitInfo.count === null
                            ? '—'
                            : permitInfo.count.toLocaleString()}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                          Latest permit date
                        </dt>
                        <dd className="text-lg text-floral_white-500">
                          {formatDate(permitInfo.date)}
                        </dd>
                      </div>
                      {permitInfo.description && (
                        <div>
                          <dt className="text-xs uppercase tracking-wide text-dust_grey-500">
                            Description
                          </dt>
                          <dd className="text-sm text-floral_white-500">
                            {permitInfo.description}
                          </dd>
                        </div>
                      )}
                    </dl>
                  )}
                </CardContent>
              </Card>

              <Card className="!border-charcoal_brown-600 !bg-charcoal_brown-400">
                <CardHeader>
                  <CardTitle className="!text-floral_white-500">Map</CardTitle>
                </CardHeader>
                <CardContent>
                  {hasAddress && mapsEmbedUrl && mapsViewUrl ? (
                    <>
                      <iframe
                        src={mapsEmbedUrl}
                        className="h-64 w-full rounded-lg border border-neutral-800"
                        loading="lazy"
                        referrerPolicy="no-referrer-when-downgrade"
                        title="Property location map"
                      />
                      <a
                        href={mapsViewUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-3 inline-flex text-xs text-neutral-400 hover:text-neutral-100"
                      >
                        View on Google Maps
                      </a>
                    </>
                  ) : (
                    <div className="flex h-64 items-center justify-center text-sm text-neutral-500">
                      Map unavailable — address not yet available for this property.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
