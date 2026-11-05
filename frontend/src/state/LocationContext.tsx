import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, post } from '../lib/api'
import { clearStored, readStored, writeStored } from '../lib/storage'
import type { Menu, Serviceability } from '../lib/types'

const KEY = 'dumdirect.location.v1'

export type Place = { name: string; city: string | null; latitude: number; longitude: number }

type Storefront =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; menu: Menu; eta: Serviceability }

type LocationValue = {
  place: Place | null
  storefront: Storefront
  choose: (place: Place) => void
  clear: () => void
  reload: () => void
}

const LocationContext = createContext<LocationValue | null>(null)

const IDLE: Storefront = { status: 'idle' }
const LOADING: Storefront = { status: 'loading' }

export function LocationProvider({ children }: { children: ReactNode }) {
  const [place, setPlace] = useState<Place | null>(() => readStored<Place | null>(KEY, null))
  const [nonce, setNonce] = useState(0)
  // The latest answer, tagged with the request it belongs to. Anything older is simply "loading".
  const [answer, setAnswer] = useState<{ key: string; result: Storefront } | null>(null)

  const key = place ? `${place.latitude},${place.longitude},${nonce}` : ''

  useEffect(() => {
    if (!place) return
    let cancelled = false
    const { latitude, longitude } = place
    Promise.all([
      api<Menu>(`/menu?latitude=${latitude}&longitude=${longitude}`),
      post<Serviceability>('/serviceability', { latitude, longitude, item_ids: [] }),
    ])
      .then(([menu, eta]) => !cancelled && setAnswer({ key, result: { status: 'ready', menu, eta } }))
      .catch((error: Error) => !cancelled && setAnswer({ key, result: { status: 'error', message: error.message } }))
    return () => {
      cancelled = true
    }
  }, [place, key])

  const storefront: Storefront = !place ? IDLE : answer?.key === key ? answer.result : LOADING

  const choose = useCallback((next: Place) => {
    setPlace(next)
    writeStored(KEY, next)
  }, [])

  const clear = useCallback(() => {
    setPlace(null)
    clearStored(KEY)
  }, [])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  const value = useMemo(() => ({ place, storefront, choose, clear, reload }), [place, storefront, choose, clear, reload])
  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>
}

export function useLocation(): LocationValue {
  const value = useContext(LocationContext)
  if (!value) throw new Error('useLocation must be used inside LocationProvider')
  return value
}
