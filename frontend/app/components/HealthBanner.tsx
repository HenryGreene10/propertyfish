'use client';

import { useEffect } from 'react';

function resolveApiBase(): string {
  const value = process.env.NEXT_PUBLIC_API_BASE;
  return value && value.trim().length > 0 ? value : 'unset';
}

export function HealthBanner() {
  const displayValue = resolveApiBase();

  useEffect(() => {
    console.log('NEXT_PUBLIC_API_BASE:', resolveApiBase());
  }, []);

  return (
    <div
      style={{
        width: '100%',
        backgroundColor: '#111',
        borderBottom: '1px solid #222',
        color: '#9ca3af',
        fontSize: '12px',
        lineHeight: 1.4,
        padding: '6px 10px',
        textAlign: 'center',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      API: {displayValue}
    </div>
  );
}
