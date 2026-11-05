/** Shapes returned by the API. Amounts are integer paise. */

export type Outlet = {
  id: number
  name: string
  kind: string
  city: string
  locality: string
  address_line: string
  fssai_no: string
  delivery_radius_km: number
}

export type Variant = { id: number; label: string; serves: number; price_paise: number }
export type Addon = { id: number; name: string; price_paise: number }

export type MenuItem = {
  id: number
  slug: string
  name: string
  description: string
  image_url: string | null
  is_veg: boolean
  spice_level: number
  allergens: string[]
  sold_out: boolean
  orderable: boolean
  variants: Variant[]
  addons: Addon[]
}

export type Category = {
  id: number
  name: string
  available_from: string | null
  available_to: string | null
  orderable_now: boolean
  items: MenuItem[]
}

export type Menu = {
  serviceable: boolean
  outlet: Outlet | null
  distance_km: number | null
  gst_note: string | null
  categories: Category[]
}

export type Serviceability = {
  serviceable: boolean
  outlet: Outlet | null
  distance_km: number | null
  eta_minutes: number | null
  cart_ok: boolean
  unavailable_item_ids: number[]
  rerouted_from: string | null
}

export type Locality = { name: string; city: string; latitude: number; longitude: number }

export type User = {
  id: number
  email: string
  name: string
  role: 'customer' | 'kitchen' | 'manager' | 'admin'
  outlet_id: number | null
  marketing_opt_in: boolean
}
