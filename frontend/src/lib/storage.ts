/** localStorage that never throws: private windows and blocked storage just behave as empty. */
export function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeStored(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable: the app still works for this visit */
  }
}

export function clearStored(key: string): void {
  try {
    window.localStorage.removeItem(key)
  } catch {
    /* nothing to clear */
  }
}
