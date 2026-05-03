import { API_BASE } from "@/lib/api/client"

export type SSEEvent = {
  type: "status_update" | "state_change" | "phase_complete" | "stream_timeout"
  status?: string
  ecm?: string
  confidence_score?: number
}

type SSEOptions = {
  genId: string
  token: string | null
  onEvent: (event: SSEEvent) => void
  onError?: (err: Event) => void
}

/**
 * Opens SSE connection to GET /api/sse/{gen_id}.
 * Returns a cleanup function — call it on component unmount.
 * Reconnects automatically with exponential backoff.
 */
export function connectSSE({
  genId,
  token,
  onEvent,
  onError,
}: SSEOptions): () => void {
  let es: EventSource | null = null
  let retryDelay = 1000       // start at 1s
  const maxDelay  = 30_000    // cap at 30s
  let stopped = false

  function connect() {
    if (stopped) return

    // Append token as query param — EventSource cannot set headers
    const url = `${API_BASE}/api/sse/${genId}${token ? `?token=${token}` : ""}`
    es = new EventSource(url)

    es.onmessage = (e) => {
      retryDelay = 1000   // reset backoff on successful message
      try {
        const parsed: SSEEvent = JSON.parse(e.data)
        // Ignore heartbeat comments — they come as empty data
        if (parsed.type) onEvent(parsed)
      } catch {
        // malformed event — ignore silently
      }
    }

    es.onerror = (err) => {
      onError?.(err)
      es?.close()
      if (!stopped) {
        setTimeout(() => {
          retryDelay = Math.min(retryDelay * 2, maxDelay)
          connect()
        }, retryDelay)
      }
    }
  }

  connect()

  // Return cleanup function for useEffect
  return () => {
    stopped = true
    es?.close()
  }
}
