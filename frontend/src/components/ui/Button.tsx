import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

type ButtonVariant = 'solid' | 'ghost';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: ButtonVariant;
  className?: string;
};

function mergeClasses(base: string, extra?: string) {
  return extra ? `${base} ${extra}` : base;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { children, className, disabled, variant = 'solid', ...props },
  ref,
) {
  const shared =
    'inline-flex items-center justify-center rounded-lg border border-neutral-700 px-4 py-2 text-sm font-medium transition-colors';
  const variants: Record<ButtonVariant, string> = {
    solid: 'bg-neutral-800 text-neutral-100 hover:bg-neutral-700 disabled:bg-neutral-900',
    ghost: 'bg-transparent text-neutral-100 hover:bg-neutral-800/40 disabled:bg-transparent',
  };

  const classes = mergeClasses(`${shared} ${variants[variant]}`, className);

  return (
    <button ref={ref} className={classes} disabled={disabled} {...props}>
      {children}
    </button>
  );
});

Button.displayName = 'Button';
