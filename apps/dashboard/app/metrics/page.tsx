import { listNiches, metricsByVideo, type VideoMetricRollup } from "../lib/api";
import { ErrorPanel } from "../components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function MetricsPage({
  searchParams,
}: {
  searchParams: Promise<{ niche?: string }>;
}) {
  const params = await searchParams;
  let niches;
  try {
    niches = await listNiches();
  } catch (err) {
    return <ErrorPanel error={err} hint="Is the API running on :8000?" />;
  }
  if (niches.length === 0) {
    return <p className="text-zinc-400">No niches. Run <code>make seed</code>.</p>;
  }
  const slug = params.niche ?? niches[0].slug;

  let rows: VideoMetricRollup[];
  try {
    rows = await metricsByVideo(slug, 100);
  } catch (err) {
    return <ErrorPanel error={err} />;
  }

  const totalViews = rows.reduce((acc, r) => acc + r.views, 0);
  const totalCost = rows.reduce((acc, r) => acc + r.cost_cents, 0);

  return (
    <main>
      <div className="mb-4 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">Metrics &mdash; {slug}</h1>
        <div className="flex gap-2 text-sm">
          {niches.map((n) => (
            <a
              key={n.slug}
              href={`/metrics?niche=${encodeURIComponent(n.slug)}`}
              className={
                "rounded px-2 py-1 border " +
                (n.slug === slug
                  ? "border-zinc-300 text-zinc-100"
                  : "border-zinc-800 text-zinc-400 hover:border-zinc-600")
              }
            >
              {n.slug}
            </a>
          ))}
        </div>
      </div>

      <p className="mb-4 text-sm text-zinc-500">
        {rows.length} video(s) &middot; total views{" "}
        <span className="text-zinc-200">{totalViews.toLocaleString()}</span> &middot;
        total cost <span className="text-zinc-200">¢{totalCost}</span>
      </p>

      {rows.length === 0 ? (
        <p className="text-zinc-400">
          No videos yet. Run <code>make e2e-stub</code>, approve, then publish.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-zinc-400">
              <tr>
                <th className="text-left p-3">Video</th>
                <th className="text-left p-3 w-32">Status</th>
                <th className="text-right p-3 w-24">Views</th>
                <th className="text-right p-3 w-20">Likes</th>
                <th className="text-right p-3 w-24">Cost (¢)</th>
                <th className="text-right p-3 w-24" title="Views per cent of actual spend — margin proxy">
                  Margin
                </th>
                <th className="text-left p-3 w-44">Last snapshot</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.video_id} className="border-t border-zinc-800">
                  <td className="p-3 font-mono text-xs">
                    {r.external_url ? (
                      <a
                        href={r.external_url}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:underline"
                      >
                        {r.video_id.slice(0, 8)}
                      </a>
                    ) : (
                      r.video_id.slice(0, 8)
                    )}
                  </td>
                  <td className="p-3 text-xs text-zinc-400">{r.status}</td>
                  <td className="p-3 text-right">{r.views.toLocaleString()}</td>
                  <td className="p-3 text-right text-zinc-400">{r.likes}</td>
                  <td className="p-3 text-right">{r.cost_cents}</td>
                  <td className="p-3 text-right">
                    <MarginCell vpc={r.views_per_cent} />
                  </td>
                  <td className="p-3 text-xs text-zinc-500">
                    {r.captured_at
                      ? new Date(r.captured_at).toLocaleString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

function MarginCell({ vpc }: { vpc: number }) {
  if (!Number.isFinite(vpc) || vpc === 0) {
    return <span className="text-zinc-600">—</span>;
  }
  const tone =
    vpc >= 100
      ? "text-emerald-400"
      : vpc >= 20
        ? "text-amber-300"
        : "text-zinc-300";
  return <span className={`font-semibold ${tone}`}>{vpc.toFixed(1)}</span>;
}
