import { useState } from 'react'

import { ItemSheet } from '../components/ItemSheet'
import { LocationPicker } from '../components/LocationPicker'
import { DishTile, ErrorNote, VegMark } from '../components/ui'
import { button } from '../components/styles'
import { formatClockIST, formatHHMM, formatPaise } from '../lib/format'
import type { Category, MenuItem, Serviceability } from '../lib/types'
import { useLocation } from '../state/LocationContext'

export function Storefront() {
  const { place, storefront } = useLocation()

  if (!place) {
    return (
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">Dum biryani from the kitchen nearest you.</h1>
          <p className="max-w-prose text-muted">Choose where it should arrive. We pick the closest kitchen that can cook your order and show how soon it reaches you.</p>
        </header>
        <LocationPicker />
      </main>
    )
  }

  if (storefront.status === 'idle' || storefront.status === 'loading') {
    return <main className="mx-auto max-w-3xl px-4 py-8"><p role="status" className="text-muted">Finding your kitchen…</p></main>
  }
  if (storefront.status === 'error') {
    return <main className="mx-auto max-w-3xl space-y-3 px-4 py-8"><ErrorNote>{storefront.message}</ErrorNote></main>
  }

  const { menu, eta } = storefront
  if (!menu.serviceable || !eta.serviceable) {
    return (
      <main className="mx-auto max-w-3xl space-y-5 px-4 py-8">
        <h1 className="text-2xl font-bold">We do not deliver to {place.name} yet.</h1>
        <p className="max-w-prose text-muted">No kitchen of ours covers that area today. Pick a nearby area and we will check again.</p>
        <LocationPicker />
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-3xl pb-28">
      <DeliveryPromise eta={eta} />
      <MenuView categories={menu.categories} gstNote={menu.gst_note} />
      {menu.outlet && (
        <footer className="px-4 py-6 text-sm text-muted">
          Cooked at {menu.outlet.name}, {menu.outlet.address_line}. FSSAI licence {menu.outlet.fssai_no}.
        </footer>
      )}
    </main>
  )
}

/** The delivery promise: the one saffron element on the page. */
function DeliveryPromise({ eta }: { eta: Serviceability }) {
  const outlet = eta.outlet!
  const minutes = eta.eta_minutes ?? 0
  const [loadedAt] = useState(() => Date.now())
  const arrival = formatClockIST(new Date(loadedAt + minutes * 60000).toISOString())
  return (
    <section aria-label="Delivery promise" className="mx-4 mt-4 flex items-center gap-5 rounded-2xl bg-ink px-5 py-4 text-white">
      <p className="font-display leading-none text-saffron">
        <span className="tabular text-6xl font-extrabold">{minutes}</span>
        <span className="ml-1 text-lg font-semibold">min</span>
      </p>
      <div className="space-y-0.5">
        <p className="font-semibold">Cooked at {outlet.name}</p>
        <p className="text-sm text-white/75">{(eta.distance_km ?? 0) < 0.2 ? 'Right next to the kitchen' : `${eta.distance_km} km away`} · arrives by about {arrival}</p>
      </div>
    </section>
  )
}

function MenuView({ categories, gstNote }: { categories: Category[]; gstNote: string | null }) {
  const [picked, setPicked] = useState<MenuItem | null>(null)
  return (
    <>
      <nav aria-label="Menu sections" className="sticky top-[53px] z-20 mt-3 border-b border-line bg-pearl/95 backdrop-blur">
        <ul className="no-scrollbar flex gap-2 overflow-x-auto px-4 py-2.5">
          {categories.map((c) => (
            <li key={c.id}>
              <a href={`#section-${c.id}`} className="inline-flex min-h-10 items-center whitespace-nowrap rounded-full border border-line bg-surface px-4 text-sm font-medium hover:bg-indigo-wash">{c.name}</a>
            </li>
          ))}
        </ul>
      </nav>

      {gstNote && <p className="px-4 pt-3 text-sm text-muted">{gstNote}</p>}

      {categories.map((category) => (
        <section key={category.id} id={`section-${category.id}`} aria-labelledby={`h-${category.id}`} className="px-4 pt-6">
          <h2 id={`h-${category.id}`} className="text-2xl font-bold">{category.name}</h2>
          {category.available_from && category.available_to && (
            <p className={'mt-0.5 text-sm ' + (category.orderable_now ? 'text-muted' : 'font-medium text-saffron-ink')}>
              {category.orderable_now
                ? `Served ${formatHHMM(category.available_from)} to ${formatHHMM(category.available_to)}`
                : `Available from ${formatHHMM(category.available_from)}`}
            </p>
          )}
          <ul className="mt-2 divide-y divide-line">
            {category.items.map((item) => (
              <li key={item.id}><ItemRow item={item} onOpen={() => setPicked(item)} /></li>
            ))}
          </ul>
        </section>
      ))}

      <ItemSheet item={picked} onClose={() => setPicked(null)} />
    </>
  )
}

function ItemRow({ item, onOpen }: { item: MenuItem; onOpen: () => void }) {
  const prices = item.variants.map((v) => v.price_paise)
  const from = Math.min(...prices)
  const label = prices.length > 1 ? `from ${formatPaise(from)}` : formatPaise(from)
  const blocked = !item.orderable

  return (
    <div className={'flex gap-4 py-4 ' + (blocked ? 'opacity-60' : '')}>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center gap-2"><VegMark veg={item.is_veg} /><h3 className="truncate font-semibold">{item.name}</h3></div>
        <p className="tabular font-medium">{label}</p>
        <p className="line-clamp-2 text-sm text-muted">{item.description}</p>
        {item.sold_out && <p className="text-sm font-medium text-late">Sold out right now</p>}
      </div>
      <div className="flex shrink-0 flex-col items-center gap-2">
        <DishTile name={item.name} src={item.image_url} tintKey={item.id} />
        <button type="button" onClick={onOpen} disabled={blocked} aria-label={`Add ${item.name}`} className={button.secondary + ' min-h-10 w-[88px] px-0 py-1.5 text-sm'}>
          {blocked ? 'Unavailable' : 'Add'}
        </button>
      </div>
    </div>
  )
}
