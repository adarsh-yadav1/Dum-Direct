import { describe, expect, it } from 'vitest'

import { STAGES, gstIncluded, isFinal, minutesPastPromise, stageIndex } from './orders'

describe('orders helpers', () => {
  it('matches the server for GST inside a 5% inclusive price', () => {
    // Same vectors as the backend tests: 105 paise contains 5 of GST.
    expect(gstIncluded(0)).toBe(0)
    expect(gstIncluded(10500)).toBe(500)
    expect(gstIncluded(100000)).toBe(4762)
    expect(gstIncluded(118000)).toBe(5619)
  })

  it('orders the stages from received to delivered', () => {
    expect(STAGES.map((s) => s.status)).toEqual(['new', 'preparing', 'ready', 'handed_off', 'completed'])
    expect(stageIndex('preparing')).toBe(1)
    expect(stageIndex('cancelled')).toBe(-1)
  })

  it('knows which orders are finished', () => {
    expect(isFinal('completed') && isFinal('cancelled') && isFinal('payment_failed')).toBe(true)
    expect(isFinal('new') || isFinal('ready') || isFinal('pending_payment')).toBe(false)
  })

  it('counts whole minutes past the promise and never goes negative', () => {
    const promised = '2026-11-05T12:00:00Z'
    const at = (min: number) => new Date('2026-11-05T12:00:00Z').getTime() + min * 60000
    expect(minutesPastPromise(promised, at(-5))).toBe(0)
    expect(minutesPastPromise(promised, at(7.9))).toBe(7)
    expect(minutesPastPromise(null, at(30))).toBe(0)
  })
})
