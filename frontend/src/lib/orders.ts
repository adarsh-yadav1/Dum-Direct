import type { OrderStatus } from './types'

/** GST contained in a GST-inclusive total (5%), rounded half up. Same integer rule as the server. */
export function gstIncluded(totalPaise: number): number {
  return Math.floor((totalPaise * 10 + 105) / 210)
}

export const STAGES: { status: OrderStatus; label: string; detail: string }[] = [
  { status: 'new', label: 'Order received', detail: 'The kitchen has your order.' },
  { status: 'preparing', label: 'Being cooked', detail: 'Your food is on the stove.' },
  { status: 'ready', label: 'Ready for pickup', detail: 'Waiting for the delivery rider.' },
  { status: 'handed_off', label: 'On the way', detail: 'The rider has your order.' },
  { status: 'completed', label: 'Delivered', detail: 'Enjoy your meal.' },
]

/** Position of a status on the tracker, or -1 when it is not part of the normal path. */
export function stageIndex(status: OrderStatus): number {
  return STAGES.findIndex((s) => s.status === status)
}

/** Orders that can still change. Everything else needs no live updates. */
export function isFinal(status: OrderStatus): boolean {
  return status === 'completed' || status === 'cancelled' || status === 'payment_failed'
}

/** Whole minutes the order is past its promised time, or 0. */
export function minutesPastPromise(promisedAt: string | null, now: number): number {
  if (!promisedAt) return 0
  return Math.max(0, Math.floor((now - new Date(promisedAt).getTime()) / 60000))
}
