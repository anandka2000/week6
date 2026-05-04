"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { submitStory, type StoryAccepted } from "../lib/api";

const MIN_LEN = 10;
const MAX_LEN = 5000;

type NicheOpt = { slug: string; name: string };

export function StoryForm({ niches }: { niches: NicheOpt[] }) {
  const [slug, setSlug] = useState<string>(niches[0]?.slug ?? "");
  const [storyText, setStoryText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StoryAccepted | null>(null);
  const [pending, startTransition] = useTransition();

  const charCount = storyText.length;
  const tooShort = charCount > 0 && charCount < MIN_LEN;
  const disabled = pending || charCount < MIN_LEN || charCount > MAX_LEN || !slug;

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setResult(null);
    const submittedSlug = slug;
    const submittedText = storyText;
    startTransition(async () => {
      try {
        const accepted = await submitStory(submittedSlug, submittedText);
        setResult(accepted);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 max-w-2xl">
      <div>
        <label htmlFor="niche" className="block text-sm text-zinc-400 mb-1">
          Niche
        </label>
        <select
          id="niche"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
          disabled={pending}
        >
          {niches.map((n) => (
            <option key={n.slug} value={n.slug}>
              {n.name} ({n.slug})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="story" className="block text-sm text-zinc-400 mb-1">
          Story text
        </label>
        <textarea
          id="story"
          rows={8}
          maxLength={MAX_LEN}
          value={storyText}
          onChange={(e) => setStoryText(e.target.value)}
          className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm font-mono"
          placeholder={`What should the script be about? (min ${MIN_LEN}, max ${MAX_LEN} chars)`}
          disabled={pending}
        />
        <div className="mt-1 text-xs text-zinc-500 flex justify-between">
          <span>
            {tooShort
              ? `Need at least ${MIN_LEN} characters.`
              : "First 80 chars become the trend title."}
          </span>
          <span>
            {charCount} / {MAX_LEN}
          </span>
        </div>
      </div>

      <button
        type="submit"
        disabled={disabled}
        className="rounded bg-emerald-700 hover:bg-emerald-600 px-4 py-2 text-sm font-medium disabled:opacity-50"
      >
        {pending ? "Generating script…" : "Generate script"}
      </button>

      {error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-3 text-sm">
          <div className="font-semibold text-red-300">Submit failed</div>
          <pre className="mt-1 whitespace-pre-wrap text-red-200 text-xs">{error}</pre>
        </div>
      ) : null}

      {result ? (
        <div className="rounded-lg border border-emerald-800 bg-emerald-950/40 p-3 text-sm">
          <div className="font-semibold text-emerald-300">
            Script accepted &mdash; status: {result.status}
          </div>
          <dl className="mt-2 space-y-1 text-xs text-emerald-100">
            <div>
              <span className="text-emerald-300/70">script_id: </span>
              <span className="font-mono">{result.script_id}</span>
            </div>
            <div>
              <span className="text-emerald-300/70">video_id: </span>
              <span className="font-mono">{result.video_id}</span>
            </div>
            <div>
              <span className="text-emerald-300/70">est. cost: </span>
              <span>¢{result.estimate_cents.toFixed(2)}</span>
            </div>
          </dl>
          <p className="mt-2 text-xs">
            <Link
              className="underline hover:text-emerald-50"
              href={`/videos?niche=${encodeURIComponent(slug)}`}
            >
              See it on /videos &rarr;
            </Link>
          </p>
        </div>
      ) : null}
    </form>
  );
}
