import { formatPaise } from '../lib/format'
import type { Order } from '../lib/types'

export function Receipt({ order }: { order: Order }) {
  return (
    <section aria-label="Order summary" className="space-y-3 rounded-xl border border-line bg-surface p-4">
      <ul className="space-y-2">
        {order.lines.map((line, index) => (
          <li key={index} className="flex justify-between gap-3">
            <span>
              {line.qty} × {line.name} <span className="text-muted">· {line.variant_label}</span>
              {line.addons.length > 0 && <span className="block text-sm text-muted">{line.addons.map((a) => a.name).join(', ')}</span>}
              {line.notes && <span className="block text-sm text-muted">Note: {line.notes}</span>}
            </span>
            <span className="tabular">{formatPaise(line.line_total_paise)}</span>
          </li>
        ))}
      </ul>
      <dl className="space-y-1 border-t border-line pt-3 text-sm">
        <Row label="Items" value={formatPaise(order.subtotal_paise)} />
        <Row label="Delivery" value={order.delivery_fee_paise === 0 ? 'Free' : formatPaise(order.delivery_fee_paise)} />
        <Row label="Total" value={formatPaise(order.total_paise)} strong />
        <p className="pt-1 text-muted">Includes {formatPaise(order.gst_included_paise)} GST.</p>
      </dl>
    </section>
  )
}

export function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={'flex justify-between ' + (strong ? 'text-base font-bold' : '')}>
      <dt>{label}</dt>
      <dd className="tabular">{value}</dd>
    </div>
  )
}
