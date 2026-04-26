import { listNiches } from "../lib/api";
import { ErrorPanel } from "../components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function NichesPage() {
  let rows;
  try {
    rows = await listNiches();
  } catch (err) {
    return <ErrorPanel error={err} hint="Is the API running on :8000?" />;
  }

  if (rows.length === 0) {
    return (
      <p className="text-zinc-400">
        No niches yet. Run <code className="text-zinc-200">make seed</code>.
      </p>
    );
  }

  return (
    <main>
      <h1 className="text-2xl font-bold mb-4">Niches</h1>
      <div className="overflow-hidden rounded-lg border border-zinc-800">
        <table className="w-full text-sm">
          <thead className="bg-zinc-900 text-zinc-400">
            <tr>
              <th className="text-left p-3">Slug</th>
              <th className="text-left p-3">Brand</th>
              <th className="text-right p-3">Cap (¢)</th>
              <th className="text-right p-3">Quota/d</th>
              <th className="text-left p-3">Voice</th>
              <th className="text-left p-3">Subreddits</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((n) => (
              <tr key={n.id} className="border-t border-zinc-800">
                <td className="p-3 font-mono">{n.slug}</td>
                <td className="p-3">{n.persona.brand}</td>
                <td className="p-3 text-right">{n.cost_cap_cents}</td>
                <td className="p-3 text-right">{n.daily_quota}</td>
                <td className="p-3 font-mono text-xs">{n.persona.voice_id}</td>
                <td className="p-3 text-xs text-zinc-400">
                  {n.persona.subreddits.join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
