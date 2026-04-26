export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-3xl font-bold">ShortStack</h1>
      <p className="mt-2 text-zinc-400">
        Day 1 skeleton. Niches, trends, and videos pages land in Day 5.
      </p>
      <ul className="mt-6 space-y-1 text-sm text-zinc-500">
        <li>API: <code className="text-zinc-300">http://localhost:8000/health</code></li>
        <li>Render: <code className="text-zinc-300">http://localhost:8787/health</code></li>
        <li>MinIO console: <code className="text-zinc-300">http://localhost:9001</code></li>
      </ul>
    </main>
  );
}
