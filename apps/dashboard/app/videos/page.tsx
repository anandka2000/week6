import { listNiches, listVideos } from "../lib/api";
import { ErrorPanel } from "../components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function VideosPage({
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

  let videos;
  try {
    videos = await listVideos(slug, 100);
  } catch (err) {
    return <ErrorPanel error={err} />;
  }

  return (
    <main>
      <h1 className="text-2xl font-bold mb-4">Videos &mdash; {slug}</h1>
      {videos.length === 0 ? (
        <p className="text-zinc-400">
          No videos yet. Pipeline lands in Phases 2&ndash;5; the approval gate stub is in
          Day 6.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-zinc-400">
              <tr>
                <th className="text-left p-3">ID</th>
                <th className="text-left p-3 w-40">Status</th>
                <th className="text-right p-3 w-28">Est. (¢)</th>
                <th className="text-right p-3 w-28">Actual (¢)</th>
                <th className="text-left p-3 w-44">Created</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v) => (
                <tr key={v.id} className="border-t border-zinc-800">
                  <td className="p-3 font-mono text-xs">{v.id.slice(0, 8)}</td>
                  <td className="p-3">{v.status}</td>
                  <td className="p-3 text-right">{v.cost_estimate_cents}</td>
                  <td className="p-3 text-right">{v.cost_cents}</td>
                  <td className="p-3 text-xs text-zinc-500">
                    {new Date(v.created_at).toLocaleString()}
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
