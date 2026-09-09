"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { clientApiBase } from "../lib/browser";

type Decision = "approve" | "reject";

export function ReviewActions({ videoId }: { videoId: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function decide(d: Decision) {
    setError(null);
    // Resolve API_BASE at click-time (not module-load) so the browser's
    // window.location is available. This is what lets an operator on a
    // MacBook hit the dashboard on anand-ubu without hard-coding a URL.
    const res = await fetch(`${clientApiBase()}/videos/${videoId}/${d}`, {
      method: "POST",
    });
    if (!res.ok) {
      setError(`${res.status} ${await res.text()}`);
      return;
    }
    startTransition(() => router.refresh());
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        disabled={pending}
        onClick={() => decide("approve")}
        className="rounded bg-emerald-700 hover:bg-emerald-600 px-3 py-1 text-xs font-medium disabled:opacity-50"
      >
        {pending ? "…" : "Approve"}
      </button>
      <button
        type="button"
        disabled={pending}
        onClick={() => decide("reject")}
        className="rounded border border-zinc-700 hover:border-zinc-500 px-3 py-1 text-xs font-medium disabled:opacity-50"
      >
        Reject
      </button>
      {error ? <span className="text-xs text-red-400">{error}</span> : null}
    </div>
  );
}
