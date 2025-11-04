import { forwardRef, type HTMLAttributes } from 'react';

function mergeClasses(base: string, extra?: string) {
  return extra ? `${base} ${extra}` : base;
}

type CardProps = HTMLAttributes<HTMLDivElement> & {
  className?: string;
};

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, ...props },
  ref,
) {
  const base =
    'rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 shadow-sm transition-shadow hover:shadow-md';
  return <div ref={ref} className={mergeClasses(base, className)} {...props} />;
});

Card.displayName = 'Card';

export const CardHeader = forwardRef<HTMLDivElement, CardProps>(function CardHeader(
  { className, ...props },
  ref,
) {
  const base = 'mb-3 flex flex-col gap-1';
  return <div ref={ref} className={mergeClasses(base, className)} {...props} />;
});

CardHeader.displayName = 'CardHeader';

export const CardTitle = forwardRef<HTMLDivElement, CardProps>(function CardTitle(
  { className, ...props },
  ref,
) {
  const base = 'text-lg font-semibold text-neutral-100';
  return <div ref={ref} className={mergeClasses(base, className)} {...props} />;
});

CardTitle.displayName = 'CardTitle';

export const CardContent = forwardRef<HTMLDivElement, CardProps>(function CardContent(
  { className, ...props },
  ref,
) {
  const base = 'flex flex-col gap-3 text-sm text-neutral-300';
  return <div ref={ref} className={mergeClasses(base, className)} {...props} />;
});

CardContent.displayName = 'CardContent';
