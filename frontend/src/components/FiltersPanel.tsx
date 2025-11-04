"use client";
import { useState } from 'react';
import type { SearchParams } from '@/lib/fetcher';

export default function FiltersPanel({ onApply }: { onApply: (p: SearchParams) => void }) {
  const [yearMin, setYearMin] = useState<number | ''>('');
  const [floorsMin, setFloorsMin] = useState<number | ''>('');
  const [unitsMin, setUnitsMin] = useState<number | ''>('');

  return (
    <div className="mb-4 flex gap-3 items-end">
      <div className="flex flex-col">
        <label className="text-sm">Year ≥</label>
        <input
          className="border rounded px-2 py-1 w-28"
          value={yearMin}
          onChange={(e) =>
            setYearMin(e.target.value === '' ? '' : Number(e.target.value))
          }
          placeholder="e.g. 1920"
        />
      </div>
      <div className="flex flex-col">
        <label className="text-sm">Floors ≥</label>
        <input
          className="border rounded px-2 py-1 w-24"
          value={floorsMin}
          onChange={(e) =>
            setFloorsMin(e.target.value === '' ? '' : Number(e.target.value))
          }
        />
      </div>
      <div className="flex flex-col">
        <label className="text-sm">Units ≥</label>
        <input
          className="border rounded px-2 py-1 w-24"
          value={unitsMin}
          onChange={(e) =>
            setUnitsMin(e.target.value === '' ? '' : Number(e.target.value))
          }
        />
      </div>
      <button
        className="px-3 py-2 bg-black text-white rounded"
        onClick={() =>
          onApply({
            limit: 20,
            offset: 0,
            year_min: yearMin === '' ? undefined : yearMin,
            floors_min: floorsMin === '' ? undefined : floorsMin,
            units_min: unitsMin === '' ? undefined : unitsMin,
          })
        }
      >
        Apply
      </button>
    </div>
  );
}
