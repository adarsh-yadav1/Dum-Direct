import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'

import { Row } from '../components/Receipt'
import { button, field } from '../components/styles'
import { ErrorNote } from '../components/ui'
import { ApiError, post } from '../lib/api'
import { formatPaise, plural } from '../lib/format'
import { gstIncluded } from '../lib/orders'
import type { Order, Serviceability } from '../lib/types'
import { useAuth } from '../state/AuthContext'
import { useCart } from '../state/CartContext'
import { useLocation } from '../state/LocationContext'

function newKey(): string {
  return typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `k${Date.now()}${Math.random().toString(36).slice(2, 12)}`
}

export function Checkout() {
  const { user, loading } = useAuth()
  const { place, clear } = useLocation()
  const { lines, totalPaise, dispatch } = useCart()
  const navigate = useNavigate()

  const [address, setAddress] = useState('')
  const [landmark, setLandmark] = useState('')
  const [check, setCheck] = useState<Serviceability | null>(null)
  const [error, setError] = useState<{ message: string; itemIds: number[]; code: string | null } | null>(null)
  const [busy, setBusy] = useState(false)
  // The same key is reused if the same order is sent again, so a retry can never double-order.
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null)

  const itemKey = [...new Set(lines.map((l) => l.itemId))].sort((a, b) => a - b).join(',')
  useEffect(() => {
    if (!place || itemKey === '') return
    let cancelled = false
    post<Serviceability>('/serviceability', {
      latitude: place.latitude,
      longitude: place.longitude,
      item_ids: itemKey.split(',').map(Number),
    })
      .then((result) => !cancelled && setCheck(result))
      .catch(() => !cancelled && setCheck(null))
    return () => {
      cancelled = true
    }
  }, [place, itemKey])

  if (loading) return <main className="mx-auto max-w-3xl px-4 py-8"><p role="status" className="text-muted">Loading…</p></main>
  if (!user) return <Navigate to="/signin?next=/checkout" replace />
  if (user.role !== 'customer') return <main className="mx-auto max-w-3xl px-4 py-8"><ErrorNote>Only customer accounts can place orders.</ErrorNote></main>
  if (!place) return <Navigate to="/" replace />
  if (lines.length === 0) return <Navigate to="/cart" replace />

  const unavailable = check?.unavailable_item_ids ?? []
  const fee = check?.outlet?.delivery_fee_paise ?? 0
  const total = totalPaise + fee

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const payload = {
      latitude: place.latitude,
      longitude: place.longitude,
      address_line: address.trim(),
      landmark: landmark.trim() || null,
      lines: lines.map((l) => ({ variant_id: l.variantId, qty: l.qty, addon_ids: l.addons.map((a) => a.id), notes: l.notes || null })),
    }
    const fingerprint = JSON.stringify(payload)
    if (attempt.current?.fingerprint !== fingerprint) attempt.current = { fingerprint, key: newKey() }
    try {
      const order = await post<Order>('/orders', payload, { 'Idempotency-Key': attempt.current.key })
      void navigate(`/orders/${order.public_code}`, { replace: true })
    } catch (e) {
      const err = e as ApiError
      if (err.status === 401) void navigate('/signin?next=/checkout')
      setError({ message: err.message, itemIds: err.itemIds ?? [], code: err.code ?? null })
      setBusy(false)
    }
  }

  const blocked = check !== null && (!check.serviceable || !check.cart_ok)
  return (
    <main className="mx-auto max-w-3xl space-y-5 px-4 py-6">
      <h1 className="text-2xl font-bold">Checkout</h1>

      {check?.serviceable === false && (
        <ErrorNote>We do not deliver to {place.name} yet. <button type="button" onClick={clear} className="font-semibold underline">Choose another area</button></ErrorNote>
      )}
      {check?.serviceable && check.outlet && (
        <p className="rounded-lg bg-indigo-wash px-4 py-3">
          {check.rerouted_from
            ? `${check.rerouted_from} cannot cook everything in your cart, so ${check.outlet.name} will cook it.`
            : `Cooked at ${check.outlet.name}.`}{' '}
          Arrives in about {check.eta_minutes} minutes.
        </p>
      )}
      {unavailable.length > 0 && (
        <div className="space-y-2">
          <ErrorNote>
            {plural(unavailable.length, 'dish', 'dishes')} in your cart cannot be cooked for this address right now:{' '}
            {lines.filter((l) => unavailable.includes(l.itemId)).map((l) => l.name).join(', ')}.
          </ErrorNote>
          <button type="button" onClick={() => dispatch({ type: 'removeItems', itemIds: unavailable })} className={button.secondary}>Remove them and continue</button>
        </div>
      )}

      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <p className="text-sm text-muted">Delivering to {place.name}.</p>
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Address</span>
          <input required minLength={5} maxLength={200} value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="street-address" placeholder="House or flat number, building, street" className={field} /></label>
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Landmark (optional)</span>
          <input maxLength={120} value={landmark} onChange={(e) => setLandmark(e.target.value)} className={field} /></label>

        <section aria-label="Bill" className="space-y-1 rounded-xl border border-line bg-surface p-4 text-sm">
          <dl className="space-y-1">
            <Row label={plural(lines.reduce((n, l) => n + l.qty, 0), 'item')} value={formatPaise(totalPaise)} />
            <Row label="Delivery" value={check ? (fee === 0 ? 'Free' : formatPaise(fee)) : '…'} />
            <Row label="Total" value={formatPaise(total)} strong />
          </dl>
          <p className="pt-1 text-muted">Includes {formatPaise(gstIncluded(total))} GST. The final amount is confirmed when you place the order.</p>
        </section>

        {error && (
          <div className="space-y-2">
            <ErrorNote>{error.message}</ErrorNote>
            {error.itemIds.length > 0 && (
              <button type="button" onClick={() => dispatch({ type: 'removeItems', itemIds: error.itemIds })} className={button.secondary}>Remove those dishes</button>
            )}
          </div>
        )}

        <div className="flex gap-3">
          <Link to="/cart" className={button.secondary}>Back to cart</Link>
          <button type="submit" disabled={busy || blocked} className={button.primary + ' flex-1'}>
            {busy ? 'Placing order…' : `Place order · ${formatPaise(total)}`}
          </button>
        </div>
      </form>
    </main>
  )
}
