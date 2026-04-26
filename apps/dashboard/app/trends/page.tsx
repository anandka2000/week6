import { listNiches, listTrends } from "../lib/api";
import { ErrorPanel } from "../components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function TrendsPage({
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

  let trends;
  try {
    trends = await listTrends(slug, 100);
  } catch (err) {
    return <ErrorPanel error={err} />;
  }

  return (
    <main>
      <div className="mb-4 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">Trends</h1>
        <div className="flex gap-2 text-sm">
          {niches.map((n) => (
            <a
              key={n.slug}
              href={`/trends?niche=${encodeURIComponent(n.slug)}`}
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

      {trends.length === 0 ? (
        <p className="text-zinc-400">
          No trends in the last 48h. Run{" "}
          <code className="text-zinc-200">make trends-fetch NICHE={slug}</code>.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-zinc-400">
              <tr>
                <th className="text-right p-3 w-16">Score</th>
                <th className="text-left p-3">Title</th>
                <th className="text-left p-3 w-24">Source</th>
                <th className="text-left p-3 w-44">Fetched</th>
              </tr>
            </thead>
            <tbody>
              {trends.map((t) => (
                <tr key={t.id} className="border-t border-zinc-800">
                  <td className="p-3 text-right">
                    <ScoreBadge score={t.hook_score} />
                  </td>
                  <td className="p-3">
                    {t.url ? (
                      <a href={t.url} target="_blank" rel="noreferrer" className="hover:underline">
                        {t.title}
                      </a>
                    ) : (
                      t.title
                    )}
                  </td>
                  <td className="p-3 text-xs text-zinc-400">{t.source}</td>
                  <td className="p-3 text-xs text-zinc-500">
                    {new Date(t.fetched_at).toLocaleString()}
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

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-zinc-600">—</span>;
  const tone =
    score >= 8
      ? "bg-emerald-900/40 text-emerald-300 border-emerald-800"
      : score >= 5
        ? "bg-amber-900/30 text-amber-200 border-amber-900"
        : "bg-zinc-800 text-zinc-300 border-zinc-700";
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold ${tone}`}>
      {score}
    </span>
  );
}
