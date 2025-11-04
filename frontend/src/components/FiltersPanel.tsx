'use client';

import React from 'react';

type FiltersValue = {
  borough?: string;
  year_built?: string;
  num_floors?: string;
  units_gte?: string;
};

type FiltersPanelProps = {
  value: FiltersValue;
  onChange: (value: FiltersValue) => void;
  onApply: () => void;
};

const BOROUGH_OPTIONS = ['', 'BK', 'QN', 'MN', 'BX', 'SI'] as const;
const BLANK_VALUES: FiltersValue = {
  borough: '',
  year_built: '',
  num_floors: '',
  units_gte: '',
};

export function FiltersPanel({ value, onChange, onApply }: FiltersPanelProps) {
  const safeValue: FiltersValue = {
    borough: value.borough ?? '',
    year_built: value.year_built ?? '',
    num_floors: value.num_floors ?? '',
    units_gte: value.units_gte ?? '',
  };

  const handleChange =
    (field: keyof FiltersValue) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      onChange({
        ...safeValue,
        [field]: event.target.value,
      });
    };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onApply();
  };

  const handleClear = () => {
    onChange({ ...BLANK_VALUES });
  };

  const formStyle: React.CSSProperties = {
    padding: '16px',
    marginBottom: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  };

  const rowStyle: React.CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '12px',
  };

  const labelStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    fontSize: '13px',
    gap: '4px',
    minWidth: '140px',
  };

  const inputStyle: React.CSSProperties = {
    backgroundColor: '#0d0d0d',
    border: '1px solid #1f2937',
    borderRadius: '10px',
    color: '#e5e5e5',
    padding: '8px 12px',
    fontSize: '14px',
  };

  const buttonsRowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  const buttonStyle: React.CSSProperties = {
    padding: '8px 14px',
    borderRadius: '10px',
    border: '1px solid #1f2937',
    background: '#1c1c1c',
    color: '#e5e5e5',
    cursor: 'pointer',
    fontSize: '14px',
  };

  const clearButtonStyle: React.CSSProperties = {
    ...buttonStyle,
    background: '#0f0f0f',
    color: '#9ca3af',
  };

  return (
    <form className="card" style={formStyle} onSubmit={handleSubmit}>
      <div style={rowStyle}>
        <label style={labelStyle}>
          <span className="muted">Borough</span>
          <select
            value={safeValue.borough}
            onChange={handleChange('borough')}
            style={inputStyle}
          >
            {BOROUGH_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt === '' ? 'Any' : opt}
              </option>
            ))}
          </select>
        </label>

        <label style={labelStyle}>
          <span className="muted">Year built</span>
          <input
            type="text"
            inputMode="numeric"
            value={safeValue.year_built}
            onChange={handleChange('year_built')}
            placeholder="e.g. 1990"
            style={inputStyle}
          />
        </label>

        <label style={labelStyle}>
          <span className="muted">Floors</span>
          <input
            type="text"
            inputMode="numeric"
            value={safeValue.num_floors}
            onChange={handleChange('num_floors')}
            placeholder="e.g. 6"
            style={inputStyle}
          />
        </label>

        <label style={labelStyle}>
          <span className="muted">Units ≥</span>
          <input
            type="text"
            inputMode="numeric"
            value={safeValue.units_gte}
            onChange={handleChange('units_gte')}
            placeholder="e.g. 10"
            style={inputStyle}
          />
        </label>
      </div>

      <div style={buttonsRowStyle}>
        <button type="button" style={clearButtonStyle} onClick={handleClear}>
          Clear
        </button>
        <button type="submit" style={buttonStyle}>
          Apply
        </button>
      </div>
    </form>
  );
}

export type { FiltersValue as FiltersPanelValue, FiltersPanelProps };
