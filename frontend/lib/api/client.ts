export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

/**
 * Fetches from FastAPI backend with JWT from localStorage.
 * Throws on non-2xx. Returns parsed JSON.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("aw_token")
    : null

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw Object.assign(new Error(body?.detail ?? res.statusText), {
      status: res.status,
      body,
    })
  }

  return res.json() as Promise<T>
}

/**
 * Typed GET helper
 */
export function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" })
}

/**
 * Typed POST helper
 */
export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  })
}
