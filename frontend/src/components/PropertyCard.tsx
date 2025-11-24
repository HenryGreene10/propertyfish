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

function formatFloorsValue(value?: number | null) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }
  return value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function formatCountValue(value?: number | null) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }
  return value.toLocaleString();
}

const VARIANTS = {
  default: {
    card: '',
    title: 'text-lg',
    subtitle: 'text-sm',
    facts: 'text-sm',
    secondary: 'text-sm',
  },
  compact: {
    card: '!px-3 !py-3',
    title: 'text-base',
    subtitle: 'text-xs',
    facts: 'text-xs',
    secondary: 'text-[11px]',
  },
} satisfies Record<'default' | 'compact', Record<string, string>>;

export default function PropertyCard({
  p,
  variant = 'default',
  className,
}: PropertyCardProps) {
  const styles = VARIANTS[variant];
  const boroughLabel = p.borough_full ?? p.borough ?? '—';
  const lotSqft = p.lot_sqft ?? p.lotarea ?? null;
  const buildingDimensions = p.building_dimensions ?? '—';
  const lotDimensions = p.lot_dimensions ?? '—';
  const lastSaleDate = p.last_sale_date ?? '—';
  const lastSalePrice =
    p.last_sale_price != null ? `$${p.last_sale_price.toLocaleString()}` : '—';
  const taxYear = p.tax_year ?? '—';
  const marketValue =
    p.market_value != null ? `$${p.market_value.toLocaleString()}` : '—';
  const taxAmount =
    p.tax_amount != null ? `$${p.tax_amount.toLocaleString()}` : '—';
  const headerFacts: string[] = [];
  const builtYearValue = formatYear(p.yearbuilt ?? p.year_built);
  if (builtYearValue !== '—') {
    headerFacts.push(`Built ${builtYearValue}`);
  }
  const floorsValue = formatFloorsValue(p.numfloors ?? p.floors ?? p.stories ?? null);
  if (floorsValue) {
    headerFacts.push(`${floorsValue} floors`);
  }
  const unitsParts: string[] = [];
  const resUnits = formatCountValue(p.unitsres);
  const totalUnits = formatCountValue(p.unitstotal ?? p.units_total);
  if (resUnits) {
    unitsParts.push(`${resUnits} res`);
  }
  if (totalUnits) {
    unitsParts.push(`${totalUnits} total`);
  }
  if (unitsParts.length > 0) {
    headerFacts.push(unitsParts.join(' / '));
  }
  const headerFactsLine = headerFacts.join(' · ');
  const zoningValue =
    p.zoning && p.zoning.trim() !== ''
      ? p.zoning
      : p.zonedist1 && p.zonedist1.trim() !== ''
        ? p.zonedist1
        : null;
  const zoning = zoningValue ?? '—';
  const landUse = p.landuse || '—';

  return (
    <Link href={`/property/${encodeURIComponent(p.bbl)}`} className="block h-full">
      <Card
        className={mergeClasses(
          'border border-charcoal_brown-600 bg-charcoal_brown-400 text-floral_white-500 transition-colors transition-shadow duration-150 hover:border-spicy_paprika-500 hover:bg-charcoal_brown-300 hover:shadow-md cursor-pointer',
          mergeClasses(styles.card, className),
        )}
      >
        <CardHeader className="gap-1">
          <CardTitle className={mergeClasses('font-semibold text-floral_white-500', styles.title)}>
            {p.address || 'Unknown address'}
          </CardTitle>
          {headerFactsLine && (
            <div className={mergeClasses('text-dust_grey-400', styles.facts)}>{headerFactsLine}</div>
          )}
          <div className={mergeClasses('text-dust_grey-500', styles.subtitle)}>{boroughLabel}</div>
        </CardHeader>
        <CardContent className="gap-1.5">
          <div className={mergeClasses('text-dust_grey-400', styles.secondary)}>
            <span className="text-spicy_paprika-500">Zoning</span> {zoning} • {landUse}
          </div>
          <div className={mergeClasses('text-dust_grey-400', styles.secondary)}>
            Building dims {buildingDimensions} • Lot{' '}
            {lotSqft != null ? `${lotSqft.toLocaleString()} sf` : '—'}
          </div>
          <div className={mergeClasses('text-dust_grey-400', styles.secondary)}>
            Lot dims {lotDimensions}
          </div>
          <div className={mergeClasses('text-dust_grey-400', styles.secondary)}>
            Last sale {lastSaleDate} • {lastSalePrice}
          </div>
          <div className={mergeClasses('text-dust_grey-400', styles.secondary)}>
            Tax year {taxYear} • Tax {taxAmount} • Market {marketValue}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
