/**
 * Shared client-side helper: pick the right API base URL from the browser's
 * perspective.
 *
 * The problem: the dashboard's server-side fetches (in server components) can
 * safely use "http://localhost:8000" because the dashboard and API run on the
 * same host. But client-side fetches from things like the Approve button run
 * in the *browser*, which may be on a different machine (e.g. accessing
 * http://anand-ubu:3000 from a MacBook). "localhost" there means the
 * MacBook, not the Ubuntu box, so the request fails with "Failed to fetch".
 *
 * Resolution order:
 *   1. NEXT_PUBLIC_API_URL — if the operator explicitly set it, honour it.
 *   2. window.location — same hostname + protocol as the dashboard, port 8000.
 *   3. localhost:8000 — SSR fallback (shouldn't actually run in the browser).
 */
export function clientApiBase(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}
