import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router'

import { Sheet } from '../components/ui'
import { api, post } from '../lib/api'
import { formatClockIST, plural } from '../lib/format'
import type { BoardOrder, Dish, OrderStatus, OutletRef } from '../lib/types'
import { chime, useBoard } from '../lib/useBoard'
import { useAuth } from '../state/AuthContext'

const COLUMNS: { status: OrderStatus; title: string; action: { label: string; to: string } | null }[] = [
  { status: 'new', title: 'New', action: { label: 'Start cooking', to: 'preparing' } },
  { status: 'preparing', title: 'Cooking', action: { label: 'Mark ready', to: 'ready' } },
  { status: 'ready', title: 'Ready', action: { label: 'Handed to rider', to: 'handed_off' } },
  { status: 'handed_off', title: 'Out for delivery', action: { label: 'Mark delivered', to: 'completed' } },
]

const press =
  'inline-flex min-h-12 items-center justify-center rounded-lg px-4 font-semibold transition-colors focus-visible:outline-saffron'

export function Kitchen() {
  const { user, loading } = useAuth()
  const [outlets, setOutlets] = useState<OutletRef[]>([])
  const [outletId, setOutletId] = useState<number | null>(null)
  const [sound, setSound] = useState(false)
  const [dishesOpen, setDishesOpen] = useState(false)

  const allowed = user !== null && user.role !== 'customer'
  useEffect(() => {
    if (!allowed) return
    api<OutletRef[]>('/outlets')
      .then((rows) => {
        setOutlets(rows)
        setOutletId((current) => current ?? rows[0]?.id ?? null)
      })
      .catch(() => setOutlets([]))
  }, [allowed])

  const onNewOrder = useCallback(() => {
    if (sound) chime()
  }, [sound])
  const { board, error, live, refresh } = useBoard(outletId, onNewOrder)

  if (loading) return <main className="min-h-dvh bg-ink p-6 text-white"><p role="status">Loading…</p></main>
  if (!user) return <Navigate to="/signin?next=/kitchen" replace />
  if (!allowed) {
    return <main className="min-h-dvh bg-ink p-6 text-white"><p>This screen is for kitchen staff. <Link to="/" className="underline">Back to the menu</Link></p></main>
  }

  const canChangePromise = user.role === 'manager' || user.role === 'admin'
  return (
    <main className="min-h-dvh bg-ink text-white">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/15 px-4 py-3">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold">Kitchen</h1>
          {outlets.length > 1 ? (
            <select aria-label="Outlet" value={outletId ?? ''} onChange={(e) => setOutletId(Number(e.target.value))} className="min-h-11 rounded-lg border border-white/30 bg-ink px-3">
              {outlets.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          ) : (
            <span className="text-white/80">{outlets[0]?.name}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span role="status" className={'inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ' + (live ? 'bg-white/10' : 'bg-saffron text-ink')}>
            <span aria-hidden="true" className={'size-2.5 rounded-full ' + (live ? 'bg-emerald-400' : 'bg-ink')} />
            {live ? 'Live' : 'Not live: refreshing every 15 seconds'}
          </span>
          <button type="button" aria-pressed={sound} onClick={() => { setSound(!sound); if (!sound) chime() }} className={press + ' border border-white/30'}>
            {sound ? 'Sound on' : 'Sound off'}
          </button>
          <button type="button" onClick={() => setDishesOpen(true)} className={press + ' border border-white/30'}>Dishes</button>
        </div>
      </header>

      {error && !board && <p role="alert" className="m-4 rounded-lg bg-late px-4 py-3">{error}</p>}
      {!board && !error && <p role="status" className="p-4 text-white/75">Loading orders…</p>}

      {board && (
        <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((column) => {
            const orders = board.orders.filter((o) => o.status === column.status)
            return (
              <section key={column.status} aria-label={column.title} className="space-y-3">
                <h2 className="font-display text-lg font-bold">{column.title} <span className="font-normal text-white/60">({orders.length})</span></h2>
                {orders.length === 0 && <p className="rounded-lg border border-dashed border-white/20 px-3 py-6 text-center text-white/50">None</p>}
                {orders.map((order) => (
                  <OrderCard key={order.public_code} order={order} outletId={outletId!} action={column.action} canChangePromise={canChangePromise} onChanged={refresh} />
                ))}
              </section>
            )
          })}
        </div>
      )}

      {outletId !== null && (
        <Sheet open={dishesOpen} onClose={() => setDishesOpen(false)} title="Dish availability">
          <Dishes outletId={outletId} />
        </Sheet>
      )}
    </main>
  )
}

function OrderCard({ order, outletId, action, canChangePromise, onChanged }: {
  order: BoardOrder
  outletId: number
  action: { label: string; to: string } | null
  canChangePromise: boolean
  onChanged: () => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [minutes, setMinutes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const late = order.promised_at ? Math.max(0, Math.floor((now - new Date(order.promised_at).getTime()) / 60000)) : 0
  const left = order.promised_at ? Math.ceil((new Date(order.promised_at).getTime() - now) / 60000) : null
  const cancellable = order.status === 'new' || order.status === 'preparing'

  const run = async (path: string, body: object) => {
    setBusy(true)
    setError(null)
    try {
      await post(`/outlets/${outletId}/orders/${order.public_code}/${path}`, body)
      await onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
      setConfirmCancel(false)
    }
  }

  return (
    <article className={'space-y-3 rounded-xl bg-white p-4 text-ink ' + (late > 0 ? 'border-l-8 border-late' : 'border-l-8 border-transparent')}>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-display text-xl font-bold">{order.public_code}</h3>
        <p className="text-sm text-muted">Placed {formatClockIST(order.placed_at)}</p>
      </div>

      {order.promised_at && (
        <p className={'font-semibold ' + (late > 0 ? 'text-late' : '')}>
          {late > 0 ? `Late by ${plural(late, 'minute')}` : left !== null && left <= 0 ? 'Due now' : `Due in ${plural(left ?? 0, 'minute')}`}
          <span className="font-normal text-muted"> · promised {formatClockIST(order.promised_at)}{order.overridden ? ' (changed by manager)' : ''}</span>
        </p>
      )}

      <ul className="space-y-1.5">
        {order.lines.map((line, i) => (
          <li key={i} className="text-lg leading-snug">
            <span className="font-bold">{line.qty} ×</span> {line.name} <span className="text-muted">· {line.variant_label}</span>
            {line.addons.length > 0 && <span className="block text-base text-muted">+ {line.addons.join(', ')}</span>}
            {line.notes && <span className="block rounded bg-warn-wash px-2 py-0.5 text-base font-medium">Note: {line.notes}</span>}
          </li>
        ))}
      </ul>

      {error && <p role="alert" className="text-sm font-medium text-late">{error}</p>}

      {action && (
        <button type="button" disabled={busy} onClick={() => void run('status', { status: action.to })} className={press + ' w-full bg-indigo text-white hover:bg-indigo-strong disabled:opacity-50'}>
          {action.label}
        </button>
      )}

      {canChangePromise && cancellable && (
        <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); void run('promise', { minutes: Number(minutes) }).then(() => setMinutes('')) }}>
          <label className="flex-1 text-sm text-muted">
            <span className="sr-only">New promised time in minutes from now</span>
            <input type="number" min={1} max={240} required value={minutes} onChange={(e) => setMinutes(e.target.value)} placeholder="Promise in … min" className="min-h-11 w-full rounded-lg border border-line px-3 text-ink" />
          </label>
          <button type="submit" disabled={busy} className={press + ' border border-line'}>Change time</button>
        </form>
      )}

      {cancellable && (
        <button type="button" disabled={busy} onClick={() => (confirmCancel ? void run('status', { status: 'cancelled' }) : setConfirmCancel(true))} className={press + ' w-full ' + (confirmCancel ? 'bg-late text-white' : 'border border-line text-late')}>
          {confirmCancel ? 'Tap again to cancel this order' : 'Cancel order'}
        </button>
      )}
    </article>
  )
}

function Dishes({ outletId }: { outletId: number }) {
  const [dishes, setDishes] = useState<Dish[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Dish[]>(`/outlets/${outletId}/items`).then(setDishes).catch((e: Error) => setError(e.message))
  }, [outletId])

  const toggle = async (dish: Dish) => {
    setError(null)
    try {
      await api(`/outlets/${outletId}/items/${dish.item_id}/availability`, { method: 'PUT', body: JSON.stringify({ is_available: !dish.is_available }) })
      setDishes((rows) => rows?.map((d) => (d.item_id === dish.item_id ? { ...d, is_available: !d.is_available } : d)) ?? null)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (error && !dishes) return <p role="alert" className="text-late">{error}</p>
  if (!dishes) return <p role="status" className="text-muted">Loading dishes…</p>
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted">Switch a dish off when it runs out. Customers stop seeing it as available straight away.</p>
      {error && <p role="alert" className="text-sm text-late">{error}</p>}
      <ul className="divide-y divide-line">
        {dishes.map((dish) => (
          <li key={dish.item_id} className="flex items-center justify-between gap-3 py-2">
            <span>{dish.name} <span className="text-sm text-muted">· {dish.category}</span></span>
            <button type="button" role="switch" aria-checked={dish.is_available} onClick={() => void toggle(dish)} className={'min-h-11 min-w-24 rounded-lg px-3 font-semibold ' + (dish.is_available ? 'bg-indigo text-white' : 'border border-line text-late')}>
              {dish.is_available ? 'Available' : 'Sold out'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
