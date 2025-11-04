import { forwardRef, type InputHTMLAttributes } from 'react';

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  className?: string;
};

function mergeClasses(base: string, extra?: string) {
  return extra ? `${base} ${extra}` : base;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, type = 'text', ...props },
  ref,
) {
  const base =
    'w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 shadow-sm focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:ring-offset-1 focus:ring-offset-neutral-950';
  return <input ref={ref} type={type} className={mergeClasses(base, className)} {...props} />;
});

Input.displayName = 'Input';
