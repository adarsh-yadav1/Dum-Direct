import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router'

import { Receipt } from '../components/Receipt'
import { button } from '../components/styles'
import { ErrorNote } from '../components/ui'
import { post } from '../lib/api'
import { formatClockIST, formatPaise } from '../lib/format'
import { STAGES, minutesPastPromise, stageIndex } from '../lib/orders'
import type { Order } from '../lib/types'
import { useLiveOrder } from '../lib/useLiveOrder'
import { useAuth } from '../state/AuthContext'
import { useCart } from '../state/CartContext'

export function OrderPage() {
  const { code = '' } = useParams()
  const { user, loading } = useAuth()
  const { order, error, setOrder } = useLiveOrder(code)

  if (loading) return <main className="mx-auto max-w-3xl px-4 py-8"><p role="status" className="text-muted">Loading…</p></main>
  if (!user) return <Navigate to={`/signin?next=/orders/${code}`} replace />
  if (error && !order) {
    return <main className="mx-auto max-w-3xl space-y-3 px-4 py-8"><ErrorNote>{error}</ErrorNote><Link to="/" className={button.secondary}>Back to the menu</Link></main>
  }
  if (!order) return <main className="mx-auto max-w-3xl px-4 py-8"><p role="status" className="text-muted">Loading your order…</p></main>

  return (
    <main className="mx-auto max-w-3xl space-y-5 px-4 py-6">
      <h1 className="text-2xl font-bold">Order {order.public_code}</h1>
      {order.status === 'pending_payment' && <Payment order={order} onUpdated={setOrder} />}
      {order.status === 'payment_failed' && <PaymentFailed />}
      {order.status === 'cancelled' && <Cancelled />}
      {stageIndex(order.status) >= 0 && <Tracker order={order} />}
      {order.rerouted_from && (
        <p className="rounded-lg bg-indigo-wash px-4 py-3 text-sm">{order.rerouted_from} could not cook every dish, so {order.outlet.name} is cooking this order.</p>
      )}
      <Receipt order={order} />
      <p className="text-sm text-muted">Cooked at {order.outlet.name}, {order.outlet.address_line}. FSSAI licence {order.outlet.fssai_no}.</p>
    </main>
  )
}

function Tracker({ order }: { order: Order }) {
  const current = stageIndex(order.status)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const late = order.status !== 'completed' && minutesPastPromise(order.promised_at, now) > 0

  return (
    <section aria-label="Order progress" className="space-y-4">
      {order.promised_at && order.status !== 'completed' && (
        <div className="rounded-2xl bg-ink px-5 py-4 text-white">
          <p className="text-sm text-white/75">{late ? 'Running a little behind' : 'Arriving by'}</p>
          <p className="tabular font-display text-4xl font-extrabold text-saffron">{formatClockIST(order.promised_at)}</p>
          {late && <p className="mt-1 text-sm text-white/75">The kitchen knows and is on it. This page updates by itself.</p>}
        </div>
      )}
      <ol className="space-y-0">
        {STAGES.map((stage, index) => {
          const done = index < current
          const here = index === current
          return (
            <li key={stage.status} aria-current={here ? 'step' : undefined} className="flex gap-3">
              <span className="flex flex-col items-center">
                <span className={'mt-1 size-4 rounded-full border-2 ' + (done ? 'border-indigo bg-indigo' : here ? 'border-indigo bg-saffron' : 'border-line bg-surface')} />
                {index < STAGES.length - 1 && <span className={'w-0.5 flex-1 ' + (done ? 'bg-indigo' : 'bg-line')} />}
              </span>
              <span className="pb-5">
                <span className={'block font-semibold ' + (done || here ? '' : 'text-muted')}>{stage.label}</span>
                {here && <span className="block text-sm text-muted">{stage.detail}</span>}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

function Payment({ order, onUpdated }: { order: Order; onUpdated: (order: Order) => void }) {
  const { dispatch } = useCart()
  const [method, setMethod] = useState<'upi' | 'card'>('upi')
  const [simulateFailure, setSimulateFailure] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pay = async () => {
    setBusy(true)
    setError(null)
    try {
      const updated = await post<Order>(`/orders/${order.public_code}/pay`, { method, outcome: simulateFailure ? 'failure' : 'success' })
      if (updated.status === 'new') dispatch({ type: 'clear' })
      onUpdated(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Payment" className="space-y-4 rounded-xl border border-line bg-surface p-4">
      <h2 className="text-lg font-bold">Pay {formatPaise(order.total_paise)}</h2>
      <fieldset className="space-y-2">
        <legend className="sr-only">Payment method</legend>
        {(['upi', 'card'] as const).map((m) => (
          <label key={m} className={'flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-3.5 py-2 ' + (method === m ? 'border-indigo bg-indigo-wash' : 'border-line')}>
            <input type="radio" name="method" checked={method === m} onChange={() => setMethod(m)} className="size-4 accent-indigo" />
            {m === 'upi' ? 'UPI' : 'Card'}
          </label>
        ))}
      </fieldset>
      <div className="rounded-lg bg-warn-wash px-3.5 py-3 text-sm">
        <p className="font-semibold">Test mode: no real money moves.</p>
        <label className="mt-2 flex items-center gap-2">
          <input type="checkbox" checked={simulateFailure} onChange={(e) => setSimulateFailure(e.target.checked)} className="size-4 accent-indigo" />
          Simulate a failed payment
        </label>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      <button type="button" onClick={() => void pay()} disabled={busy} className={button.primary + ' w-full'}>{busy ? 'Paying…' : `Pay ${formatPaise(order.total_paise)}`}</button>
    </section>
  )
}

function PaymentFailed() {
  return (
    <div className="space-y-3">
      <ErrorNote>The payment did not go through and nothing was charged. This order was not sent to the kitchen.</ErrorNote>
      <Link to="/cart" className={button.primary}>Back to your cart</Link>
    </div>
  )
}

function Cancelled() {
  return <ErrorNote>The kitchen cancelled this order. If you paid, your refund will follow in 5 to 7 working days.</ErrorNote>
}
