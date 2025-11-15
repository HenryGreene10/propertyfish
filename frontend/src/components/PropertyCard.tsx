import Link from 'next/link';

import type { PropertySummary } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';

type PropertyCardProps = {
  p: PropertySummary;
  variant?: 'compact' | 'default';
  className?: string;
};

function mergeClasses(base: string, extra?: string) {
  return extra ? `${base} ${extra}` : base;
}

function formatMetric(value?: number | null, suffix?: string) {
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

const VARIANTS = {
  default: {
    card: '',
    title: 'text-lg',
    subtitle: 'text-sm text-neutral-400',
    facts: 'text-sm text-neutral-200',
    secondary: 'text-xs text-neutral-400',
  },
  compact: {
    card: '!px-3 !py-3',
    title: 'text-base',
    subtitle: 'text-xs text-neutral-400',
    facts: 'text-xs text-neutral-200',
    secondary: 'text-[11px] text-neutral-400',
  },
} satisfies Record<'default' | 'compact', Record<string, string>>;

export default function PropertyCard({
  p,
  variant = 'default',
  className,
}: PropertyCardProps) {
  const styles = VARIANTS[variant];
  const boroughLabel = p.borough_full ?? p.borough ?? '—';
  const yearBuilt = formatYear(p.yearbuilt ?? p.year_built);
  const floors = formatMetric(p.numfloors ?? p.floors);
  const units = formatMetric(p.unitstotal ?? p.units_total);
  const zoning = p.zonedist1 || '—';
  const landUse = p.landuse || '—';

  return (
    <Link href={`/property/${encodeURIComponent(p.bbl)}`} className="block">
      <Card className={mergeClasses(styles.card, className)}>
        <CardHeader className="gap-1">
          <CardTitle className={styles.title}>{p.address || 'Unknown address'}</CardTitle>
          <div className={styles.subtitle}>{boroughLabel}</div>
        </CardHeader>
        <CardContent className="gap-1.5">
          <div className={styles.facts}>
            Built {yearBuilt} • {floors} floors • {units} units
          </div>
          <div className={styles.secondary}>
            Zoning {zoning} • {landUse}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
