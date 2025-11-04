export default function PropertyCard({ p }: { p: any }) {
  return (
    <div className="border rounded-lg p-4 shadow-sm">
      <div className="font-semibold">{p.address ?? 'Unknown address'}</div>
      <div className="text-sm opacity-80">BBL: {p.bbl}</div>
      <div className="text-sm mt-1">
        Year: {p.year_built ?? '—'} · Floors: {p.floors ?? '—'} · Units: {p.units ?? '—'}
      </div>
    </div>
  );
}
