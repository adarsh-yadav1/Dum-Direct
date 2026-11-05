import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import type { Locality } from '../lib/types'
import { useLocation, type Place } from '../state/LocationContext'
import { ErrorNote } from './ui'
import { button, field } from './styles'

/** Search the areas we know, or use the phone's position. Nothing is stored on the server. */
export function LocationPicker({ onPicked }: { onPicked?: () => void }) {
  const { choose } = useLocation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Locality[]>([])
  const [error, setError] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)

  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      api<Locality[]>(`/localities?q=${encodeURIComponent(query)}&limit=20`)
        .then((rows) => {
          if (!cancelled) {
            setResults(rows)
            setError(null)
          }
        })
        .catch((e: Error) => !cancelled && setError(e.message))
    }, 200)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [query])

  const pick = (place: Place) => {
    choose(place)
    onPicked?.()
  }

  const useMyPosition = () => {
    if (!('geolocation' in navigator)) {
      setError('This browser cannot share your position. Pick your area from the list.')
      return
    }
    setLocating(true)
    setError(null)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false)
        pick({ name: 'Your location', city: null, latitude: position.coords.latitude, longitude: position.coords.longitude })
      },
      () => {
        setLocating(false)
        setError('Could not get your position. Allow location access, or pick your area from the list.')
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    )
  }

  return (
    <div className="space-y-3">
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium text-muted">Delivery area</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your area, for example Kondapur"
          autoComplete="off"
          className={field}
        />
      </label>

      <button type="button" onClick={useMyPosition} disabled={locating} className={button.secondary + ' w-full'}>
        {locating ? 'Finding you…' : 'Use my current location'}
      </button>

      {error && <ErrorNote>{error}</ErrorNote>}

      <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
        {results.map((r) => (
          <li key={`${r.city}-${r.name}`}>
            <button
              type="button"
              onClick={() => pick({ name: r.name, city: r.city, latitude: r.latitude, longitude: r.longitude })}
              className="flex min-h-12 w-full items-center justify-between gap-3 px-3.5 py-2 text-left hover:bg-indigo-wash"
            >
              <span className="font-medium">{r.name}</span>
              <span className="text-sm text-muted">{r.city}</span>
            </button>
          </li>
        ))}
        {results.length === 0 && !error && (
          <li className="px-3.5 py-3 text-sm text-muted">No area matches “{query}”. Try the first letters of its name.</li>
        )}
      </ul>
    </div>
  )
}
