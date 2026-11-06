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
  delivery_fee_paise: number
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

export type OrderLine = {
  name: string
  variant_label: string
  qty: number
  unit_price_paise: number
  line_total_paise: number
  addons: { name: string; price_paise: number }[]
  notes: string | null
}

export type OrderStatus =
  | 'pending_payment'
  | 'payment_failed'
  | 'new'
  | 'preparing'
  | 'ready'
  | 'handed_off'
  | 'completed'
  | 'cancelled'

export type Order = {
  public_code: string
  status: OrderStatus
  outlet: Outlet
  distance_km: number | null
  rerouted_from: string | null
  lines: OrderLine[]
  subtotal_paise: number
  delivery_fee_paise: number
  total_paise: number
  gst_included_paise: number
  placed_at: string
  promised_at: string | null
  payment: { method: string; status: string; amount_paise: number } | null
  last_event_id: number
}

export type BoardLine = { name: string; variant_label: string; qty: number; addons: string[]; notes: string | null }

export type BoardOrder = {
  public_code: string
  status: OrderStatus
  placed_at: string
  promised_at: string | null
  minutes_late: number
  late_alerted: boolean
  overridden: boolean
  lines: BoardLine[]
}

export type Board = { outlet_id: number; cursor: number; orders: BoardOrder[] }
export type OutletRef = { id: number; name: string; city: string }
export type Dish = { item_id: number; name: string; category: string; is_available: boolean }
