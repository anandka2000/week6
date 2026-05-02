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
