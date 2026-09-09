import { clientApiBase } from "./browser";

// Server-side base: this file is imported by server components (page.tsx) whose
// fetches run on the same host as the API, so localhost is safe there. Client-
// side callers (StoryForm etc.) must go through clientApiBase() so a browser
// on a *different* machine hits the API by its real hostname — see browser.ts.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET ${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type Niche = {
  id: string;
  slug: string;
  name: string;
  cost_cap_cents: number;
  daily_quota: number;
  persona: {
    brand: string;
    voice_id: string;
    tone: string;
    hook_styles: string[];
    banned_topics: string[];
    cta_template: string;
    subreddits: string[];
  };
  created_at: string;
};

export type Trend = {
  id: string;
  source: "reddit" | "youtube" | "gtrends";
  title: string;
  url: string | null;
  hook_score: number | null;
  cluster_id: string | null;
  fetched_at: string;
  consumed_at: string | null;
};

export type Video = {
  id: string;
  niche_id: string;
  status: string;
  cost_estimate_cents: number;
  cost_cents: number;
  duration_sec: string | null;
  s3_key_mp4: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type DailyCost = { day: string; total_cents: number };

export type StoryAccepted = {
  script_id: string;
  video_id: string;
  estimate_cents: number;
  status: string;
};

export type VideoMetricRollup = {
  video_id: string;
  status: string;
  external_url: string | null;
  cost_cents: number;
  cost_estimate_cents: number;
  views: number;
  likes: number;
  comments: number;
  captured_at: string | null;
  views_per_cent: number;
};

export const listNiches = () => get<Niche[]>("/niches");
export const listTrends = (slug: string, limit = 50) =>
  get<Trend[]>(`/trends?niche=${encodeURIComponent(slug)}&limit=${limit}`);
export const listVideos = (slug: string, limit = 50) =>
  get<Video[]>(`/videos?niche=${encodeURIComponent(slug)}&limit=${limit}`);
export const dailyCosts = (slug: string, days = 30) =>
  get<DailyCost[]>(`/costs/daily?niche=${encodeURIComponent(slug)}&days=${days}`);
export const metricsByVideo = (slug: string, limit = 50) =>
  get<VideoMetricRollup[]>(
    `/metrics/by-video?niche=${encodeURIComponent(slug)}&limit=${limit}`,
  );

async function _readApiError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    // FastAPI Pydantic validation error: detail is an array of {loc, msg, type, ...}
    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const where = Array.isArray(d.loc) ? d.loc.join(".") : "";
          return where ? `${where}: ${d.msg ?? "invalid"}` : (d.msg ?? "invalid");
        })
        .join("; ");
    }
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    try {
      return await res.text();
    } catch {
      return `(unparseable ${res.status} body)`;
    }
  }
}

export async function submitStory(
  nicheSlug: string,
  storyText: string,
): Promise<StoryAccepted> {
  // Runs in the browser (StoryForm is a client component), so derive the API
  // base from window.location — a MacBook hitting http://anand-ubu:3000 must
  // POST to http://anand-ubu:8000, not http://localhost:8000.
  const res = await fetch(`${clientApiBase()}/videos/from-story`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ niche_slug: nicheSlug, story_text: storyText }),
  });
  if (!res.ok) {
    throw new Error(
      `POST /videos/from-story (${res.status}): ${await _readApiError(res)}`,
    );
  }
  return res.json() as Promise<StoryAccepted>;
}
