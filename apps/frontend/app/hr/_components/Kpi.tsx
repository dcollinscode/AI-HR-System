export default function Kpi({
  label,
  value,
  icon,
  tone,
  hint,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  tone: string;
  hint?: string;
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-zinc-500">{label}</span>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${tone}`}>
          {icon}
        </span>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-zinc-900 tabular-nums">
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-zinc-400">{hint}</p> : null}
    </div>
  );
}