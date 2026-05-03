"use client"

type ConfidenceBand = "green" | "yellow" | "red" | "unknown"

type Props = {
  band: ConfidenceBand
  children: React.ReactNode
  className?: string
}

const RING_STYLES: Record<ConfidenceBand, string> = {
  green:   "ring-2 ring-green-400  shadow-[0_0_16px_2px_rgba(74,222,128,0.35)]",
  yellow:  "ring-2 ring-yellow-400 shadow-[0_0_16px_2px_rgba(250,204,21,0.35)]",
  red:     "ring-2 ring-red-400    shadow-[0_0_16px_2px_rgba(248,113,113,0.35)]",
  unknown: "ring-2 ring-zinc-600",
}

export function ConfidenceBorder({ band, children, className = "" }: Props) {
  return (
    <div
      className={`rounded-xl transition-all duration-500 ${RING_STYLES[band]} ${className}`}
    >
      {children}
    </div>
  )
}
