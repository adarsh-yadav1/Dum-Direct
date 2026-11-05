import { describe, expect, it } from 'vitest'

import { formatClockIST, formatHHMM, formatPaise, plural } from './format'

describe('format', () => {
  it('shows whole rupees without decimals and uses Indian grouping', () => {
    expect(formatPaise(32000)).toBe('₹320')
    expect(formatPaise(118000)).toBe('₹1,180')
    expect(formatPaise(12345678)).toBe('₹1,23,456.78')
  })

  it('keeps paise when they are not whole', () => {
    expect(formatPaise(32050)).toBe('₹320.50')
  })

  it('shows clock time in IST whatever the viewer zone', () => {
    expect(formatClockIST('2026-11-05T14:15:00Z')).toBe('7:45 pm')
    expect(formatClockIST('2026-11-05T18:30:00Z')).toBe('12:00 am')
  })

  it('turns window times into plain words', () => {
    expect(formatHHMM('16:00')).toBe('4 pm')
    expect(formatHHMM('23:30')).toBe('11:30 pm')
    expect(formatHHMM('00:00')).toBe('12 am')
    expect(formatHHMM('12:05')).toBe('12:05 pm')
  })

  it('pluralises', () => {
    expect(plural(1, 'item')).toBe('1 item')
    expect(plural(2, 'item')).toBe('2 items')
  })
})
