import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router'

import { button, field } from '../components/styles'
import { ErrorNote, Sheet, VegMark } from '../components/ui'
import { api, post } from '../lib/api'
import { formatPaise } from '../lib/format'
import type { AdminItem, AdminMenu, AdminVariant } from '../lib/types'
import { useAuth } from '../state/AuthContext'

const toPaise = (rupees: string) => Math.round(Number(rupees) * 100)
const send = (path: string, method: string, body?: unknown) =>
  api(path, { method, body: body === undefined ? undefined : JSON.stringify(body) })

export function Admin() {
  const { user, loading } = useAuth()
  const [menu, setMenu] = useState<AdminMenu | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const load = useCallback(async () => {
    try {
      setMenu(await api<AdminMenu>('/admin/menu'))
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])
  useEffect(() => {
    if (user?.role === 'admin') void load()
  }, [user, load])

  if (loading) return <main className="mx-auto max-w-3xl px-4 py-8"><p role="status" className="text-muted">Loading…</p></main>
  if (!user) return <Navigate to="/signin?next=/admin" replace />
  if (user.role !== 'admin') return <main className="mx-auto max-w-3xl px-4 py-8"><ErrorNote>Only admins can edit the menu.</ErrorNote></main>

  return (
    <main className="mx-auto max-w-4xl space-y-5 px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Menu admin</h1>
          <p className="text-sm text-muted">One menu for every outlet. Changes reach customers straight away.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/kitchen" className={button.secondary}>Kitchen screen</Link>
          <button type="button" onClick={() => setAdding(true)} className={button.primary}>Add a dish</button>
        </div>
      </header>
      {error && <ErrorNote>{error}</ErrorNote>}
      {!menu && !error && <p role="status" className="text-muted">Loading the menu…</p>}
      {menu?.categories.map((category) => (
        <section key={category.id} aria-label={category.name} className="space-y-2">
          <h2 className="text-xl font-bold">{category.name}</h2>
          <ul className="space-y-2">
            {category.items.map((item) => <li key={item.id}><ItemEditor item={item} menu={menu} onChanged={load} /></li>)}
          </ul>
        </section>
      ))}
      {menu && (
        <Sheet open={adding} onClose={() => setAdding(false)} title="Add a dish">
          <NewDish menu={menu} onDone={() => { setAdding(false); void load() }} />
        </Sheet>
      )}
    </main>
  )
}

function Saved({ state }: { state: string | null }) {
  return <p role="status" aria-live="polite" className="min-h-5 text-sm text-muted">{state}</p>
}

function ItemEditor({ item, menu, onChanged }: { item: AdminItem; menu: AdminMenu; onChanged: () => Promise<void> }) {
  const [note, setNote] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)

  const apply = async (action: () => Promise<unknown>, done: string) => {
    setFailure(null)
    try {
      await action()
      setNote(done)
      await onChanged()
    } catch (e) {
      setNote(null)
      setFailure((e as Error).message)
    }
  }

  return (
    <details className={'rounded-xl border border-line bg-surface ' + (item.is_active ? '' : 'opacity-70')}>
      <summary className="flex min-h-12 cursor-pointer items-center justify-between gap-3 px-4 py-2">
        <span className="flex items-center gap-2 font-semibold"><VegMark veg={item.is_veg} />{item.name}{!item.is_active && <span className="text-sm font-normal text-late"> · hidden from customers</span>}</span>
        <span className="tabular text-sm text-muted">{item.variants.map((v) => formatPaise(v.price_paise)).join(' / ')}</span>
      </summary>
      <div className="space-y-5 border-t border-line p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => void apply(() => send(`/admin/items/${item.id}`, 'PATCH', { is_active: !item.is_active }), item.is_active ? 'Hidden from customers.' : 'Visible to customers.')} className={button.secondary}>
            {item.is_active ? 'Hide from customers' : 'Show to customers'}
          </button>
          <Saved state={note} />
        </div>
        {failure && <ErrorNote>{failure}</ErrorNote>}

        <fieldset className="space-y-3">
          <legend className="font-display font-semibold">Prices (rupees, GST included)</legend>
          {item.variants.map((v) => <PriceRow key={v.id} variant={v} cities={menu.cities} apply={apply} />)}
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="font-display font-semibold">Offered at</legend>
          <ul className="grid gap-2 sm:grid-cols-2">
            {menu.outlets.map((outlet) => {
              const row = item.outlets.find((o) => o.outlet_id === outlet.id)
              const listed = row?.listed ?? false
              return (
                <li key={outlet.id}>
                  <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-line px-3">
                    <input type="checkbox" checked={listed} onChange={() => void apply(() => send(`/admin/outlets/${outlet.id}/items/${item.id}`, 'PUT', { listed: !listed }), listed ? `Removed from ${outlet.name}.` : `Now offered at ${outlet.name}.`)} className="size-4 accent-indigo" />
                    <span>{outlet.name} <span className="text-sm text-muted">· {outlet.city}</span></span>
                  </label>
                </li>
              )
            })}
          </ul>
        </fieldset>
      </div>
    </details>
  )
}

function PriceRow({ variant, cities, apply }: { variant: AdminVariant; cities: string[]; apply: (action: () => Promise<unknown>, done: string) => Promise<void> }) {
  const [base, setBase] = useState(String(variant.price_paise / 100))
  const [byCity, setByCity] = useState<Record<string, string>>(() => Object.fromEntries(cities.map((c) => [c, variant.city_prices[c] !== undefined ? String(variant.city_prices[c] / 100) : ''])))

  const saveBase = (e: FormEvent) => {
    e.preventDefault()
    void apply(() => send(`/admin/variants/${variant.id}`, 'PATCH', { price_paise: toPaise(base) }), `${variant.label} price saved.`)
  }
  const saveCity = (city: string) => {
    const value = byCity[city]
    return value === ''
      ? apply(() => send(`/admin/variants/${variant.id}/city-prices/${encodeURIComponent(city)}`, 'DELETE'), `${city} now uses the standard price.`)
      : apply(() => send(`/admin/variants/${variant.id}/city-prices/${encodeURIComponent(city)}`, 'PUT', { price_paise: toPaise(value) }), `${city} price saved.`)
  }

  return (
    <div className="space-y-2 rounded-lg bg-pearl p-3">
      <form onSubmit={saveBase} className="flex flex-wrap items-end gap-2">
        <label className="flex-1 text-sm"><span className="mb-1 block font-medium">{variant.label} <span className="text-muted">· serves {variant.serves} · standard price</span></span>
          <input type="number" min={1} max={10000} step="0.5" required value={base} onChange={(e) => setBase(e.target.value)} className={field} /></label>
        <button type="submit" className={button.secondary}>Save</button>
      </form>
      <div className="grid gap-2 sm:grid-cols-2">
        {cities.map((city) => (
          <form key={city} onSubmit={(e) => { e.preventDefault(); void saveCity(city) }} className="flex items-end gap-2">
            <label className="flex-1 text-sm"><span className="mb-1 block text-muted">{city} (blank = standard)</span>
              <input type="number" min={1} max={10000} step="0.5" value={byCity[city]} onChange={(e) => setByCity({ ...byCity, [city]: e.target.value })} className={field} /></label>
            <button type="submit" className={button.quiet}>Save</button>
          </form>
        ))}
      </div>
    </div>
  )
}

function NewDish({ menu, onDone }: { menu: AdminMenu; onDone: () => void }) {
  const [categoryId, setCategoryId] = useState(menu.categories[0]?.id ?? 0)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [veg, setVeg] = useState(true)
  const [spice, setSpice] = useState(1)
  const [prep, setPrep] = useState('20')
  const [allergens, setAllergens] = useState('')
  const [image, setImage] = useState('')
  const [portions, setPortions] = useState([{ label: 'Regular', serves: '1', price: '' }])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await post('/admin/items', {
        category_id: categoryId, name, description, is_veg: veg, spice_level: spice, base_prep_minutes: Number(prep),
        allergens: allergens.split(',').map((a) => a.trim()).filter(Boolean), image_url: image.trim() || null,
        variants: portions.map((p) => ({ label: p.label, serves: Number(p.serves), price_paise: toPaise(p.price) })),
      })
      onDone()
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }
  const setPortion = (i: number, patch: Partial<(typeof portions)[number]>) => setPortions(portions.map((p, j) => (j === i ? { ...p, ...patch } : p)))

  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-4">
      <p className="text-sm text-muted">A new dish is not offered anywhere until you tick the outlets that cook it.</p>
      <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Section</span>
        <select value={categoryId} onChange={(e) => setCategoryId(Number(e.target.value))} className={field}>{menu.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Name</span>
        <input required minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} className={field} /></label>
      <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Description</span>
        <textarea maxLength={500} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} className={field} /></label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Type</span>
          <select value={veg ? 'veg' : 'non'} onChange={(e) => setVeg(e.target.value === 'veg')} className={field}><option value="veg">Vegetarian</option><option value="non">Non-vegetarian</option></select></label>
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Spice</span>
          <select value={spice} onChange={(e) => setSpice(Number(e.target.value))} className={field}>{['Mild', 'Medium', 'Hot', 'Very hot'].map((s, i) => <option key={s} value={i}>{s}</option>)}</select></label>
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Cooking time (minutes)</span>
          <input type="number" min={1} max={180} required value={prep} onChange={(e) => setPrep(e.target.value)} className={field} /></label>
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Allergens (comma separated)</span>
          <input value={allergens} onChange={(e) => setAllergens(e.target.value)} placeholder="milk, egg" className={field} /></label>
      </div>
      <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Photo link (optional, Unsplash, Pexels or Wikimedia)</span>
        <input type="url" value={image} onChange={(e) => setImage(e.target.value)} className={field} /></label>
      <fieldset className="space-y-2">
        <legend className="font-display font-semibold">Portions</legend>
        {portions.map((p, i) => (
          <div key={i} className="grid grid-cols-[1fr_5rem_6rem] gap-2">
            <input aria-label="Portion name" required value={p.label} onChange={(e) => setPortion(i, { label: e.target.value })} className={field} />
            <input aria-label="Serves" type="number" min={1} max={20} required value={p.serves} onChange={(e) => setPortion(i, { serves: e.target.value })} className={field} />
            <input aria-label="Price in rupees" type="number" min={1} max={10000} step="0.5" required placeholder="₹" value={p.price} onChange={(e) => setPortion(i, { price: e.target.value })} className={field} />
          </div>
        ))}
        {portions.length < 6 && <button type="button" onClick={() => setPortions([...portions, { label: '', serves: '1', price: '' }])} className={button.quiet}>Add a portion</button>}
      </fieldset>
      {error && <ErrorNote>{error}</ErrorNote>}
      <button type="submit" disabled={busy} className={button.primary + ' w-full'}>{busy ? 'Saving…' : 'Add dish'}</button>
    </form>
  )
}
