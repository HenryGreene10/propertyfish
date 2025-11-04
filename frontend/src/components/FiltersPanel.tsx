'use client';

import { FormEvent, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import type { SearchFilters } from '@/lib/types';

type FiltersPanelProps = {
  onApply: (p: Partial<SearchFilters>) => void;
};

export default function FiltersPanel({ onApply }: FiltersPanelProps) {
  const [yearMin, setYearMin] = useState<number | ''>('');
  const [floorsMin, setFloorsMin] = useState<number | ''>('');
  const [unitsMin, setUnitsMin] = useState<number | ''>('');

  const handleApply = () => {
    onApply({
      limit: 20,
      offset: 0,
      year_min: yearMin === '' ? undefined : yearMin,
      floors_min: floorsMin === '' ? undefined : floorsMin,
      units_min: unitsMin === '' ? undefined : unitsMin,
    });
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    handleApply();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mb-6 rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 shadow-sm"
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4 sm:items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-neutral-500">Year ≥</label>
          <Input
            type="number"
            inputMode="numeric"
            value={yearMin}
            onChange={(e) =>
              setYearMin(e.target.value === '' ? '' : Number(e.target.value))
            }
            placeholder="e.g. 1920"
            className="sm:w-full"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-neutral-500">Floors ≥</label>
          <Input
            type="number"
            inputMode="numeric"
            value={floorsMin}
            onChange={(e) =>
              setFloorsMin(e.target.value === '' ? '' : Number(e.target.value))
            }
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-neutral-500">Units ≥</label>
          <Input
            type="number"
            inputMode="numeric"
            value={unitsMin}
            onChange={(e) =>
              setUnitsMin(e.target.value === '' ? '' : Number(e.target.value))
            }
          />
        </div>
        <div className="flex items-end">
          <Button className="w-full sm:w-auto" type="submit">
            Apply
          </Button>
        </div>
      </div>
    </form>
  );
}
