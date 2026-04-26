export function ErrorPanel({ error, hint }: { error: unknown; hint?: string }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm">
      <div className="font-semibold text-red-300">Failed to load</div>
      <pre className="mt-1 whitespace-pre-wrap text-red-200">{msg}</pre>
      {hint ? <p className="mt-2 text-red-300/80">{hint}</p> : null}
    </div>
  );
}
