export default function Loading() {
  return (
    <div className="min-h-screen bg-zinc-950 flex items-center 
                    justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-72 h-72 rounded-xl bg-zinc-800 animate-pulse" />
        <div className="h-4 w-48 bg-zinc-800 rounded animate-pulse" />
        <div className="h-10 w-64 bg-zinc-800 rounded-lg animate-pulse" />
      </div>
    </div>
  )
}
