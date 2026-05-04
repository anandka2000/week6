import Link from "next/link";

import { listNiches } from "../lib/api";
import { ErrorPanel } from "../components/ErrorPanel";
import { StoryForm } from "./StoryForm";

export const dynamic = "force-dynamic";

export default async function StoriesPage() {
  let niches;
  try {
    niches = await listNiches();
  } catch (err) {
    return <ErrorPanel error={err} hint="Is the API running on :8000?" />;
  }

  if (niches.length === 0) {
    return (
      <p className="text-zinc-400">
        No niches yet. Run <code className="text-zinc-200">make seed</code>.
      </p>
    );
  }

  return (
    <main>
      <h1 className="text-2xl font-bold mb-2">User-story mode</h1>
      <p className="text-sm text-zinc-400 mb-6">
        Skip trend discovery and feed the script generator your own story. The
        pipeline runs the same Sonnet prompt + downstream stages
        (assets &rarr; render &rarr; review &rarr; publish). Once submitted,
        track progress on <Link className="underline hover:text-zinc-100" href="/videos">/videos</Link>.
      </p>
      <StoryForm niches={niches.map((n) => ({ slug: n.slug, name: n.name }))} />
    </main>
  );
}
