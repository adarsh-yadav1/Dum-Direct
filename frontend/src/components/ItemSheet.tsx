import { useState } from 'react'

import { formatPaise, plural } from '../lib/format'
import type { MenuItem } from '../lib/types'
import { MAX_QTY_PER_LINE } from '../state/cart'
import { useCart } from '../state/CartContext'
import { Sheet, VegMark } from './ui'
import { button, field } from './styles'

const SPICE = ['Mild', 'Medium spice', 'Hot', 'Very hot']

export function ItemSheet({ item, onClose }: { item: MenuItem | null; onClose: () => void }) {
  return (
    <Sheet open={item !== null} onClose={onClose} title={item?.name ?? ''}>
      {item && <ItemForm key={item.id} item={item} onDone={onClose} />}
    </Sheet>
  )
}

function ItemForm({ item, onDone }: { item: MenuItem; onDone: () => void }) {
  const { dispatch } = useCart()
  const [variantId, setVariantId] = useState(item.variants[0].id)
  const [addonIds, setAddonIds] = useState<number[]>([])
  const [notes, setNotes] = useState('')
  const [qty, setQty] = useState(1)

  const variant = item.variants.find((v) => v.id === variantId) ?? item.variants[0]
  const chosen = item.addons.filter((a) => addonIds.includes(a.id))
  const unit = variant.price_paise + chosen.reduce((sum, a) => sum + a.price_paise, 0)

  const add = () => {
    dispatch({
      type: 'add',
      line: {
        itemId: item.id,
        variantId: variant.id,
        name: item.name,
        variantLabel: variant.label,
        unitPricePaise: variant.price_paise,
        addons: chosen.map((a) => ({ id: a.id, name: a.name, pricePaise: a.price_paise })),
        notes,
        qty,
      },
    })
    onDone()
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-sm text-muted">
        <VegMark veg={item.is_veg} />
        <span>{SPICE[item.spice_level] ?? SPICE[0]}</span>
        {item.allergens.length > 0 && <span>· Contains {item.allergens.join(', ')}</span>}
      </div>
      <p className="text-muted">{item.description}</p>

      <fieldset className="space-y-2">
        <legend className="mb-1 font-display font-semibold">Portion</legend>
        {item.variants.map((v) => (
          <label key={v.id} className={'flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-lg border px-3.5 py-2 ' + (v.id === variantId ? 'border-indigo bg-indigo-wash' : 'border-line')}>
            <span className="flex items-center gap-3">
              <input type="radio" name="variant" checked={v.id === variantId} onChange={() => setVariantId(v.id)} className="size-4 accent-indigo" />
              <span>
                <span className="font-medium">{v.label}</span>
                <span className="ml-2 text-sm text-muted">serves {v.serves}</span>
              </span>
            </span>
            <span className="tabular font-medium">{formatPaise(v.price_paise)}</span>
          </label>
        ))}
      </fieldset>

      {item.addons.length > 0 && (
        <fieldset className="space-y-2">
          <legend className="mb-1 font-display font-semibold">Add-ons</legend>
          {item.addons.map((a) => (
            <label key={a.id} className="flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-lg border border-line px-3.5 py-2">
              <span className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={addonIds.includes(a.id)}
                  onChange={(e) => setAddonIds(e.target.checked ? [...addonIds, a.id] : addonIds.filter((id) => id !== a.id))}
                  className="size-4 accent-indigo"
                />
                {a.name}
              </span>
              <span className="tabular text-muted">+{formatPaise(a.price_paise)}</span>
            </label>
          ))}
        </fieldset>
      )}

      <label className="block">
        <span className="mb-1.5 block font-display font-semibold">Note for the kitchen</span>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={200} rows={2} placeholder="For example: less spicy" className={field} />
      </label>

      <div className="flex items-center gap-3">
        <Stepper qty={qty} onChange={setQty} label={`Quantity of ${item.name}`} />
        <button type="button" onClick={add} className={button.primary + ' flex-1'}>
          Add {plural(qty, 'item')} · {formatPaise(unit * qty)}
        </button>
      </div>
    </div>
  )
}

export function Stepper({ qty, onChange, label, min = 1 }: { qty: number; onChange: (qty: number) => void; label: string; min?: number }) {
  return (
    <div role="group" aria-label={label} className="inline-flex items-center rounded-lg border border-line bg-surface">
      <button type="button" aria-label="One less" onClick={() => onChange(qty - 1)} disabled={qty <= min && min > 0} className="min-h-11 min-w-11 text-lg font-semibold disabled:opacity-40">−</button>
      <output aria-live="polite" className="tabular min-w-8 text-center font-semibold">{qty}</output>
      <button type="button" aria-label="One more" onClick={() => onChange(Math.min(MAX_QTY_PER_LINE, qty + 1))} disabled={qty >= MAX_QTY_PER_LINE} className="min-h-11 min-w-11 text-lg font-semibold disabled:opacity-40">+</button>
    </div>
  )
}
