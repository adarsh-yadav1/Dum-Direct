import { useState } from 'react'
import { Link, Outlet, useLocation as useRoute } from 'react-router'

import { useAuth } from '../state/AuthContext'
import { useCart } from '../state/CartContext'
import { useLocation } from '../state/LocationContext'
import { formatPaise, plural } from '../lib/format'
import { LocationPicker } from './LocationPicker'
import { Logo, Sheet } from './ui'
import { button } from './styles'

export function Layout() {
  const { place } = useLocation()
  const { user, logout } = useAuth()
  const { count, totalPaise } = useCart()
  const [changing, setChanging] = useState(false)
  const route = useRoute()
  const showCartBar = count > 0 && route.pathname === '/'

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-2.5">
          <Link to="/" aria-label="DumDirect home"><Logo /></Link>
          <div className="flex items-center gap-1">
            {place && (
              <button type="button" onClick={() => setChanging(true)} className={button.quiet + ' max-w-44 gap-1.5'} aria-label={`Delivering to ${place.name}. Change area`}>
                <svg width="14" height="16" viewBox="0 0 14 16" aria-hidden="true" className="shrink-0"><path d="M7 0a6 6 0 0 0-6 6c0 4.2 6 10 6 10s6-5.8 6-10a6 6 0 0 0-6-6Zm0 8.2A2.2 2.2 0 1 1 7 3.8a2.2 2.2 0 0 1 0 4.4Z" fill="currentColor" /></svg>
                <span className="truncate">{place.name}</span>
              </button>
            )}
            {user ? (
              <button type="button" onClick={() => void logout()} className={button.quiet}>Sign out</button>
            ) : (
              <Link to="/signin" className={button.quiet}>Sign in</Link>
            )}
          </div>
        </div>
      </header>

      <Outlet />

      <Sheet open={changing} onClose={() => setChanging(false)} title="Delivery area">
        <LocationPicker onPicked={() => setChanging(false)} />
      </Sheet>

      {showCartBar && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
            <p className="tabular font-semibold">{plural(count, 'item')} · {formatPaise(totalPaise)}</p>
            <Link to="/cart" className={button.primary}>View cart</Link>
          </div>
        </div>
      )}
    </>
  )
}
