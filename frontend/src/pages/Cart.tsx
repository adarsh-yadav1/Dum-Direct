import { Link } from 'react-router'

import { Stepper } from '../components/ItemSheet'
import { button } from '../components/styles'
import { formatPaise, plural } from '../lib/format'
import { lineTotal, unitTotal } from '../state/cart'
import { useCart } from '../state/CartContext'

export function Cart() {
  const { lines, count, totalPaise, dispatch } = useCart()

  if (lines.length === 0) {
    return (
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-8">
        <h1 className="text-2xl font-bold">Your cart is empty</h1>
        <p className="text-muted">Add a dish from the menu and it will appear here.</p>
        <Link to="/" className={button.primary}>Browse the menu</Link>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-3xl space-y-5 px-4 py-6">
      <h1 className="text-2xl font-bold">Your cart</h1>
      <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
        {lines.map((line) => (
          <li key={line.key} className="flex items-start justify-between gap-3 p-4">
            <div className="min-w-0 space-y-1">
              <p className="font-semibold">{line.name} <span className="font-normal text-muted">· {line.variantLabel}</span></p>
              {line.addons.length > 0 && <p className="text-sm text-muted">{line.addons.map((a) => a.name).join(', ')}</p>}
              {line.notes && <p className="text-sm text-muted">Note: {line.notes}</p>}
              <p className="tabular text-sm text-muted">{formatPaise(unitTotal(line))} each</p>
              <button type="button" onClick={() => dispatch({ type: 'remove', key: line.key })} className="text-sm font-medium text-late underline">Remove</button>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-2">
              <Stepper qty={line.qty} min={0} onChange={(qty) => dispatch({ type: 'setQty', key: line.key, qty })} label={`Quantity of ${line.name}`} />
              <p className="tabular font-semibold">{formatPaise(lineTotal(line))}</p>
            </div>
          </li>
        ))}
      </ul>
      <div className="flex items-center justify-between rounded-xl bg-indigo-wash px-4 py-3">
        <p className="font-semibold">{plural(count, 'item')}</p>
        <p className="tabular text-lg font-bold">{formatPaise(totalPaise)}</p>
      </div>
      <p className="text-sm text-muted">Delivery fee and the final total are confirmed when you place the order.</p>
      <div className="flex gap-3">
        <Link to="/" className={button.secondary}>Add more</Link>
      </div>
    </main>
  )
}
