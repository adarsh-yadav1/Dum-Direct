import { useEffect, useState } from 'react'

import { api } from './lib/api'

type ApiState = 'checking' | 'online' | 'offline'

function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')

  useEffect(() => {
    let cancelled = false
    api<{ status: string }>('/health')
      .then(() => !cancelled && setApiState('online'))
      .catch(() => !cancelled && setApiState('offline'))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-10">
      <header className="space-y-2">
        <p className="text-sm font-medium tracking-wide text-accent uppercase">DumDirect</p>
        <h1 className="text-3xl font-semibold text-ink">Hyderabadi food, ordered directly.</h1>
        <p className="text-muted">
          The ordering app is being built. This page confirms that the frontend and the API are
          connected.
        </p>
      </header>

      <div
        role="status"
        aria-live="polite"
        className="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3"
      >
        <span
          aria-hidden="true"
          className={
            'size-2.5 rounded-full ' +
            (apiState === 'online'
              ? 'bg-veg'
              : apiState === 'offline'
                ? 'bg-late'
                : 'bg-warn')
          }
        />
        <span className="text-sm text-ink">
          {apiState === 'checking' && 'Checking the API…'}
          {apiState === 'online' && 'API is online'}
          {apiState === 'offline' && 'API is not reachable. Start the backend and reload.'}
        </span>
      </div>
    </main>
  )
}

export default App
