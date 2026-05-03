"use client"
import { useEffect, useState } from "react"
import { apiGet, apiPost } from "@/lib/api/client"
import { connectSSE } from "@/lib/sse/client"
import { ConfidenceBorder } from "@/components/shared/ConfidenceBorder"

type ConfidenceBand = "green" | "yellow" | "red" | "unknown"

type GenerationData = {
  gen_id: string
  status: string
  confidence_score: number | null
  confidence_band: ConfidenceBand
  isolated_png_url: string | null
  source_url: string | null
  product_brief: Record<string, unknown> | null
  agent_motion_suggestion: string | null
  director_tips: Array<{ tip_type: string; copy_en: string }>
}

type Props = {
  genId: string
  onContinue: () => void   // called after successful /advance
  onReupload: () => void   // called when user clicks Re-upload
}

const HEADLINE: Record<ConfidenceBand, string> = {
  green:   "Looks good — we isolated your product.",
  yellow:  "Edges look thin — double-check before continuing.",
  red:     "We had trouble isolating the product. Try re-uploading with a plain background.",
  unknown: "Processing your product...",
}

export function HD2Isolation({ genId, onContinue, onReupload }: Props) {
  const [data, setData] = useState<GenerationData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [imageView, setImageView] = useState<"isolated" | "source">("isolated")
  const [advancing, setAdvancing] = useState(false)

  useEffect(() => {
    // STEP 1: GET hydration FIRST
    apiGet<GenerationData>(`/api/generations/${genId}`)
      .then(fetchedData => {
        setData(fetchedData)
        setLoading(false)

        // STEP 2: SSE attach AFTER GET completes
        const token = localStorage.getItem("aw_token")
        const cleanup = connectSSE({
          genId,
          token,
          onEvent: (event) => {
            if (event.type === "phase_complete" && event.status === "brief_ready") {
              // Re-fetch to get latest data
              apiGet<GenerationData>(`/api/generations/${genId}`)
                .then(setData)
                .catch(console.error)
            }
            if (event.type === "state_change" && event.status === "scripting") {
              onContinue()
            }
          },
        })
        return cleanup
      })
      .catch(err => {
        setError(err.message ?? "Failed to load generation")
        setLoading(false)
      })
  }, [genId, onContinue])

  async function handleAdvance() {
    setAdvancing(true)
    try {
      await apiPost(`/api/generations/${genId}/advance`)
      // SSE will fire state_change → scripting → onContinue() called
      // If SSE misses it, navigate anyway after short delay
      setTimeout(onContinue, 3000)
    } catch (err: unknown) {
      const e = err as { status?: number; body?: { error?: string } }
      if (e.status === 409) {
        // Already advancing — wait for SSE
      } else {
        setError("Failed to advance. Please try again.")
        setAdvancing(false)
      }
    }
  }

  // Loading state
  if (loading) return (
    <div className="flex items-center justify-center min-h-screen bg-zinc-950">
      <div className="text-zinc-400 animate-pulse">Preparing your isolation...</div>
    </div>
  )

  // Error state  
  if (error || !data) return (
    <div className="flex items-center justify-center min-h-screen bg-zinc-950">
      <div className="text-red-400 text-center">
        <p>{error || "No data available"}</p>
        <button onClick={onReupload} className="mt-4 underline text-zinc-400">
          Try re-uploading
        </button>
      </div>
    </div>
  )

  // Main render (data is loaded):
  const band = data.confidence_band
  const showSource = imageView === "source"
  const imageUrl = showSource ? data.source_url : data.isolated_png_url

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center 
                    justify-center px-4 py-12 gap-8">

      {/* Headline */}
      <h2 className="text-white text-xl font-medium text-center max-w-md">
        {HEADLINE[band]}
      </h2>

      {/* Image with confidence ring */}
      <ConfidenceBorder band={band} className="p-1">
        <div
          className="relative w-72 h-72 rounded-lg overflow-hidden"
          style={{
            // Checkerboard background pattern for transparency
            backgroundImage: `
              linear-gradient(45deg, #3f3f3f 25%, transparent 25%),
              linear-gradient(-45deg, #3f3f3f 25%, transparent 25%),
              linear-gradient(45deg, transparent 75%, #3f3f3f 75%),
              linear-gradient(-45deg, transparent 75%, #3f3f3f 75%)
            `,
            backgroundSize: "20px 20px",
            backgroundPosition: "0 0, 0 10px, 10px -10px, -10px 0px",
            backgroundColor: "#2a2a2a",
          }}
        >
          {imageUrl ? (
            <img
              src={imageUrl}
              alt="Product isolation"
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center 
                            text-zinc-600 text-sm">
              No image available
            </div>
          )}
        </div>
      </ConfidenceBorder>

      {/* Source / Isolated toggle */}
      <div className="flex gap-2 bg-zinc-900 rounded-lg p-1">
        {(["isolated", "source"] as const).map((view) => (
          <button
            key={view}
            onClick={() => setImageView(view)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all
              ${imageView === view
                ? "bg-zinc-700 text-white"
                : "text-zinc-400 hover:text-zinc-200"
              }`}
          >
            {view === "isolated" ? "Isolated" : "Source"}
          </button>
        ))}
      </div>

      {/* Director Tips (if any) */}
      {data.director_tips.length > 0 && (
        <div className="max-w-sm w-full space-y-2">
          {data.director_tips.map((tip, i) => (
            <div key={i} className="text-zinc-400 text-sm bg-zinc-900 
                                     rounded-lg px-4 py-2">
              <span className="text-zinc-500 uppercase text-xs 
                               tracking-wide mr-2">
                {tip.tip_type}
              </span>
              {tip.copy_en}
            </div>
          ))}
        </div>
      )}

      {/* CTA Buttons — logic per [PRD-HD2] confidence gating */}
      <div className="flex gap-3 mt-2">
        {band === "red" ? (
          // Red band: Re-upload is primary, Continue Anyway is secondary
          <>
            <button
              onClick={onReupload}
              className="px-6 py-2.5 bg-white text-zinc-900 rounded-lg 
                         font-medium hover:bg-zinc-100 transition-colors"
            >
              ↻ Re-upload
            </button>
            <button
              onClick={handleAdvance}
              disabled={advancing}
              className="px-6 py-2.5 bg-zinc-800 text-zinc-300 rounded-lg 
                         font-medium hover:bg-zinc-700 transition-colors
                         disabled:opacity-50"
            >
              {advancing ? "Processing..." : "Continue Anyway"}
            </button>
          </>
        ) : (
          // Green or Yellow: Continue is primary, Re-upload is secondary
          <>
            <button
              onClick={onReupload}
              className="px-6 py-2.5 bg-zinc-800 text-zinc-300 rounded-lg 
                         font-medium hover:bg-zinc-700 transition-colors"
            >
              ↻ Re-upload
            </button>
            <button
              onClick={handleAdvance}
              disabled={advancing}
              className="px-6 py-2.5 bg-white text-zinc-900 rounded-lg 
                         font-medium hover:bg-zinc-100 transition-colors
                         disabled:opacity-50"
            >
              {advancing ? "Processing..." : "✓ Continue to Scripts →"}
            </button>
          </>
        )}
      </div>

    </div>
  )
}
