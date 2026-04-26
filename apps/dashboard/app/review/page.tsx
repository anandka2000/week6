import { listNiches, type Video } from "../lib/api";
import { ErrorPanel } from "../components/ErrorPanel";
import { ReviewActions } from "./ReviewActions";

export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function listPendingReview(slug: string): Promise<Video[]> {
  const res = await fetch(
    `${API_BASE}/videos?niche=${encodeURIComponent(slug)}&statuses=pending_review`,
    { cache: "no-store" }
  );
  if (!res.ok) throw new Error(`GET /videos -> ${res.status}`);
  return res.json();
}

export default async function ReviewPage({
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

  let pending;
  try {
    pending = await listPendingReview(slug);
  } catch (err) {
    return <ErrorPanel error={err} />;
  }

  return (
    <main>
      <h1 className="text-2xl font-bold mb-1">Review &mdash; {slug}</h1>
      <p className="text-sm text-zinc-500 mb-4">
        {pending.length} video(s) waiting for human approval before publish.
      </p>

      {pending.length === 0 ? (
        <p className="text-zinc-400">
          Nothing pending. Run <code>make e2e-stub</code> to drop one in.
        </p>
      ) : (
        <ul className="space-y-3">
          {pending.map((v) => (
            <li
              key={v.id}
              className="rounded-lg border border-zinc-800 p-4 flex items-center justify-between"
            >
              <div>
                <div className="font-mono text-xs text-zinc-400">{v.id}</div>
                <div className="text-sm mt-1">
                  est. ¢{v.cost_estimate_cents} &middot; actual ¢{v.cost_cents} &middot;{" "}
                  {new Date(v.created_at).toLocaleString()}
                </div>
              </div>
              <ReviewActions videoId={v.id} />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
