// fields: year_built, floors, units_total, permit_count_12m
import type { SearchCard } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';

type PropertyCardProps = {
  p: SearchCard;
  variant?: 'compact' | 'default';
  className?: string;
};

function mergeClasses(base: string, extra?: string) {
  return extra ? `${base} ${extra}` : base;
}

function formatLastPermitDate(input?: string | null) {
  if (!input) return '—';
  const parsed = new Date(input);
  if (Number.isNaN(parsed.getTime())) {
    return '—';
  }
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const VARIANTS = {
  default: {
    card: '',
    title: 'text-lg',
    subtitle: 'text-sm text-neutral-400',
    chipWrap: 'flex flex-wrap gap-2',
    chip: 'rounded-full border border-neutral-700 bg-neutral-800/60 px-3 py-1 text-xs font-medium text-neutral-200',
    meta: 'text-xs text-neutral-500',
  },
  compact: {
    card: '!px-3 !py-3',
    title: 'text-base',
    subtitle: 'text-xs text-neutral-400',
    chipWrap: 'flex flex-wrap gap-1.5',
    chip: 'rounded-md border border-neutral-700/70 bg-neutral-800/40 px-2.5 py-0.5 text-[11px] font-medium text-neutral-200',
    meta: 'text-[11px] text-neutral-500',
  },
} satisfies Record<'default' | 'compact', Record<string, string>>;

export default function PropertyCard({
  p,
  variant = 'default',
  className,
}: PropertyCardProps) {
  const styles = VARIANTS[variant];
  const boroughLabel = p.borough_full ?? p.borough ?? '—';
  const subtitle = [boroughLabel, p.bbl ? `BBL ${p.bbl}` : null].filter(Boolean).join(' • ');

  const metrics = [
    { label: 'Year ≥', value: p.year_built ?? '—' },
    { label: 'Floors ≥', value: p.floors ?? '—' },
    { label: 'Units ≥', value: p.units_total ?? '—' },
    { label: 'Permits (12m)', value: p.permit_count_12m ?? 0 },
  ];
  const lastPermit = formatLastPermitDate(p.last_permit_date);

  return (
    <Card className={mergeClasses(styles.card, className)}>
      <CardHeader className="gap-1">
        <CardTitle className={styles.title}>{p.address || 'Unknown address'}</CardTitle>
        <div className={styles.subtitle}>{subtitle}</div>
      </CardHeader>
      <CardContent className="gap-2">
        <div className={styles.chipWrap}>
          {metrics.map(({ label, value }) => (
            <span key={label} className={styles.chip}>
              {label}: {value}
            </span>
          ))}
        </div>
        <div className={styles.meta}>
          Last permit: {lastPermit}
        </div>
      </CardContent>
    </Card>
  );
}
