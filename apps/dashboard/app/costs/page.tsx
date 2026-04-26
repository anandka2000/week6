import { dailyCosts, listNiches } from "../lib/api";
import { ErrorPanel } from "../components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function CostsPage({
  searchParams,
}: {
  searchParams: Promise<{ niche?: string }>;
}) {
  const params = await searchParams;
  let niches;
  try {
    niches = await listNiches();
  } catch (err) {
    return <ErrorPanel error={err} />;
  }
  if (niches.length === 0) {
    return <p className="text-zinc-400">No niches. Run <code>make seed</code>.</p>;
  }
  const slug = params.niche ?? niches[0].slug;

  let rows;
  try {
    rows = await dailyCosts(slug, 30);
  } catch (err) {
    return <ErrorPanel error={err} />;
  }

  const total = rows.reduce((acc, r) => acc + r.total_cents, 0);
  const max = Math.max(1, ...rows.map((r) => r.total_cents));

  return (
    <main>
      <h1 className="text-2xl font-bold mb-1">Costs &mdash; {slug}</h1>
      <p className="text-sm text-zinc-500 mb-4">
        Last 30 days &middot; {rows.length} day(s) with spend &middot; total ¢{total.toFixed(2)}
      </p>

      {rows.length === 0 ? (
        <p className="text-zinc-400">
          No cost events yet. Run trends-cluster to spend Haiku tokens; the rest
          comes online with Phase 2.
        </p>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.day} className="flex items-center gap-3">
              <span className="w-24 font-mono text-xs text-zinc-400">{r.day}</span>
              <div className="h-4 flex-1 rounded bg-zinc-900 overflow-hidden">
                <div
                  className="h-full bg-emerald-700"
                  style={{ width: `${(r.total_cents / max) * 100}%` }}
                />
              </div>
              <span className="w-20 text-right font-mono text-xs">
                ¢{r.total_cents.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
