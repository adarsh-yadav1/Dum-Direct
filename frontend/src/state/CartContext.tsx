import { createContext, useContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'

import { readStored, writeStored } from '../lib/storage'
import { cartCount, cartReducer, cartTotal, type CartAction, type CartLine } from './cart'

const KEY = 'dumdirect.cart.v1'

type CartValue = { lines: CartLine[]; count: number; totalPaise: number; dispatch: Dispatch<CartAction> }

const CartContext = createContext<CartValue | null>(null)

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, dispatch] = useReducer(cartReducer, undefined, () => readStored<CartLine[]>(KEY, []))

  useEffect(() => writeStored(KEY, lines), [lines])

  const value = useMemo(
    () => ({ lines, count: cartCount(lines), totalPaise: cartTotal(lines), dispatch }),
    [lines],
  )
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart(): CartValue {
  const value = useContext(CartContext)
  if (!value) throw new Error('useCart must be used inside CartProvider')
  return value
}
