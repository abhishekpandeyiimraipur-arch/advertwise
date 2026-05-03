"use client"
import { useParams, useRouter } from "next/navigation"
import { HD2Isolation } from "@/components/hd/HD2Isolation"

export default function GenerationPage() {
  const params  = useParams()
  const router  = useRouter()
  const genId   = params.gen_id as string

  function handleContinue() {
    // Phase 2 built in next micro-phase
    // For now: show a placeholder
    router.push(`/${genId}?stage=scripting`)
  }

  function handleReupload() {
    // Return to HD1 — built in a future slice
    router.push("/")
  }

  return (
    <HD2Isolation
      genId={genId}
      onContinue={handleContinue}
      onReupload={handleReupload}
    />
  )
}
