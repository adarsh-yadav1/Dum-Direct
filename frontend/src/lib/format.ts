const rupees = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })

/** 118000 -> "₹1,180". Whole rupees drop the decimals; anything else keeps two. */
export function formatPaise(paise: number): string {
  const value = paise / 100
  return Number.isInteger(value)
    ? rupees.format(value).replace(/\.00$/, '')
    : rupees.format(value)
}

/** Clock time in India, for example "7:45 pm". India has no daylight saving. */
export function formatClockIST(iso: string): string {
  return new Intl.DateTimeFormat('en-IN', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'Asia/Kolkata',
  })
    .format(new Date(iso))
    .replace(/\s?([ap])m$/i, (_, letter: string) => ` ${letter.toLowerCase()}m`)
}

/** "16:00" -> "4 pm", "23:30" -> "11:30 pm". */
export function formatHHMM(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number)
  const suffix = h >= 12 ? 'pm' : 'am'
  const hour = h % 12 === 0 ? 12 : h % 12
  return m === 0 ? `${hour} ${suffix}` : `${hour}:${String(m).padStart(2, '0')} ${suffix}`
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`
}
