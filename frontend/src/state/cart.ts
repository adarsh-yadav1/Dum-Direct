/** Cart logic, kept free of React so it can be tested on its own. Prices shown here are only
 *  a preview: the server recomputes every price when the order is placed. */

export type CartAddon = { id: number; name: string; pricePaise: number }

export type CartLine = {
  key: string
  itemId: number
  variantId: number
  name: string
  variantLabel: string
  unitPricePaise: number // portion price, before add-ons
  addons: CartAddon[]
  notes: string
  qty: number
}

export const MAX_QTY_PER_LINE = 20
export const MAX_LINES = 30

export function lineKey(variantId: number, addonIds: number[], notes: string): string {
  return [variantId, [...addonIds].sort((a, b) => a - b).join('.'), notes.trim().toLowerCase()].join('|')
}

export function unitTotal(line: CartLine): number {
  return line.unitPricePaise + line.addons.reduce((sum, a) => sum + a.pricePaise, 0)
}

export function lineTotal(line: CartLine): number {
  return unitTotal(line) * line.qty
}

export function cartTotal(lines: CartLine[]): number {
  return lines.reduce((sum, line) => sum + lineTotal(line), 0)
}

export function cartCount(lines: CartLine[]): number {
  return lines.reduce((sum, line) => sum + line.qty, 0)
}

export type CartAction =
  | { type: 'add'; line: Omit<CartLine, 'key'> }
  | { type: 'setQty'; key: string; qty: number }
  | { type: 'remove'; key: string }
  | { type: 'removeItems'; itemIds: number[] }
  | { type: 'clear' }

export function cartReducer(lines: CartLine[], action: CartAction): CartLine[] {
  switch (action.type) {
    case 'add': {
      const notes = action.line.notes.trim()
      const key = lineKey(action.line.variantId, action.line.addons.map((a) => a.id), notes)
      const existing = lines.find((l) => l.key === key)
      if (existing) {
        return lines.map((l) =>
          l.key === key ? { ...l, qty: Math.min(MAX_QTY_PER_LINE, l.qty + action.line.qty) } : l,
        )
      }
      if (lines.length >= MAX_LINES) return lines
      return [...lines, { ...action.line, notes, key, qty: Math.min(MAX_QTY_PER_LINE, action.line.qty) }]
    }
    case 'setQty':
      return action.qty <= 0
        ? lines.filter((l) => l.key !== action.key)
        : lines.map((l) => (l.key === action.key ? { ...l, qty: Math.min(MAX_QTY_PER_LINE, action.qty) } : l))
    case 'remove':
      return lines.filter((l) => l.key !== action.key)
    case 'removeItems':
      return lines.filter((l) => !action.itemIds.includes(l.itemId))
    case 'clear':
      return []
  }
}
