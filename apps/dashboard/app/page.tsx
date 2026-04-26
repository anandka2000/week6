import Link from "next/link";

export default function Home() {
  return (
    <main>
      <h1 className="text-3xl font-bold">ShortStack</h1>
      <p className="mt-2 text-zinc-400">
        AI short-video pipeline for Trending Tech. Pick a section in the nav.
      </p>
      <ul className="mt-6 space-y-2">
        {[
          { href: "/niches", label: "Niches", hint: "Brand + voice + cost cap" },
          { href: "/trends", label: "Trends", hint: "Recent (48h) topics, scored 1-10" },
          { href: "/videos", label: "Videos", hint: "Pipeline + status + cost" },
          { href: "/costs", label: "Costs", hint: "Daily spend by niche" },
        ].map((l) => (
          <li key={l.href}>
            <Link
              href={l.href}
              className="block rounded-md border border-zinc-800 p-3 hover:border-zinc-600 transition-colors"
            >
              <div className="font-medium">{l.label}</div>
              <div className="text-xs text-zinc-500">{l.hint}</div>
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-xs text-zinc-600">
        API: <code>http://localhost:8000</code> &middot; Render:{" "}
        <code>http://localhost:8787</code> &middot; MinIO:{" "}
        <code>http://localhost:9001</code>
      </p>
    </main>
  );
}
