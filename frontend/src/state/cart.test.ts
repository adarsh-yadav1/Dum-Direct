import { describe, expect, it } from 'vitest'

import { MAX_LINES, MAX_QTY_PER_LINE, cartCount, cartReducer, cartTotal, lineKey, lineTotal, type CartLine } from './cart'

const base: Omit<CartLine, 'key'> = {
  itemId: 1,
  variantId: 10,
  name: 'Chicken dum biryani',
  variantLabel: 'Regular',
  unitPricePaise: 32000,
  addons: [],
  notes: '',
  qty: 1,
}

const add = (lines: CartLine[], over: Partial<typeof base> = {}) =>
  cartReducer(lines, { type: 'add', line: { ...base, ...over } })

describe('cart', () => {
  it('adds a line and totals it with add-ons', () => {
    const lines = add([], { addons: [{ id: 5, name: 'Extra raita', pricePaise: 3000 }], qty: 2 })
    expect(lineTotal(lines[0])).toBe((32000 + 3000) * 2)
    expect(cartTotal(lines)).toBe(70000)
    expect(cartCount(lines)).toBe(2)
  })

  it('merges the same dish, portion, add-ons and note', () => {
    const lines = add(add([]))
    expect(lines).toHaveLength(1)
    expect(lines[0].qty).toBe(2)
  })

  it('treats add-on order and note case as the same line', () => {
    expect(lineKey(1, [3, 2], ' Less Spicy ')).toBe(lineKey(1, [2, 3], 'less spicy'))
  })

  it('keeps different portions, add-ons or notes apart', () => {
    let lines = add([])
    lines = add(lines, { variantId: 11 })
    lines = add(lines, { addons: [{ id: 5, name: 'x', pricePaise: 100 }] })
    lines = add(lines, { notes: 'less spicy' })
    expect(lines).toHaveLength(4)
  })

  it('caps the quantity of a line', () => {
    const lines = add([], { qty: MAX_QTY_PER_LINE })
    expect(add(lines)[0].qty).toBe(MAX_QTY_PER_LINE)
  })

  it('stops adding new lines at the limit', () => {
    let lines: CartLine[] = []
    for (let i = 0; i < MAX_LINES + 5; i++) lines = add(lines, { variantId: 100 + i })
    expect(lines).toHaveLength(MAX_LINES)
  })

  it('removes a line when its quantity reaches zero', () => {
    const lines = add([])
    expect(cartReducer(lines, { type: 'setQty', key: lines[0].key, qty: 0 })).toEqual([])
  })

  it('removes all lines of dishes that are no longer available', () => {
    let lines = add([])
    lines = add(lines, { itemId: 2, variantId: 20 })
    expect(cartReducer(lines, { type: 'removeItems', itemIds: [2] }).map((l) => l.itemId)).toEqual([1])
  })

  it('clears', () => {
    expect(cartReducer(add([]), { type: 'clear' })).toEqual([])
  })
})
