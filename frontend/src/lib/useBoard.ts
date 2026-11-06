import { useCallback, useEffect, useRef, useState } from 'react'

import { API_BASE_URL, api } from './api'
import type { Board } from './types'

const POLL_MS = 15_000

/**
 * The kitchen board for one outlet, kept current by a live stream, with a 15-second re-read as
 * the safety net. `live` says whether the stream is connected, so staff know if they are
 * looking at a live board or one that refreshes every 15 seconds.
 */
export function useBoard(outletId: number | null, onNewOrder: () => void) {
  const [board, setBoard] = useState<Board | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(false)
  const cursor = useRef<number | null>(null)
  const announce = useRef(onNewOrder)
  useEffect(() => {
    announce.current = onNewOrder
  }, [onNewOrder])

  const refresh = useCallback(async () => {
    if (outletId === null) return
    try {
      const next = await api<Board>(`/outlets/${outletId}/orders`)
      cursor.current ??= next.cursor
      setBoard(next)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [outletId])

  useEffect(() => {
    cursor.current = null
    void refresh()
  }, [refresh])

  const ready = board !== null && board.outlet_id === outletId
  useEffect(() => {
    if (outletId === null || !ready) return
    const timer = window.setInterval(() => void refresh(), POLL_MS)
    let source: EventSource | null = null
    if (typeof EventSource !== 'undefined') {
      source = new EventSource(`${API_BASE_URL}/outlets/${outletId}/stream?after=${cursor.current ?? 0}`, { withCredentials: true })
      source.onopen = () => setLive(true)
      source.onerror = () => setLive(false)
      source.onmessage = (message: MessageEvent<string>) => {
        try {
          if ((JSON.parse(message.data) as { type?: string }).type === 'order_new') announce.current()
        } catch {
          /* an unreadable event is ignored; the refresh below still runs */
        }
        void refresh()
      }
    }
    return () => {
      window.clearInterval(timer)
      source?.close()
      setLive(false)
    }
  }, [outletId, ready, refresh])

  return { board: ready ? board : null, error, live, refresh }
}

/** A short two-tone chime for a new order, made with the browser's audio so no file is needed. */
export function chime(): void {
  try {
    const context = new AudioContext()
    ;[880, 1175].forEach((frequency, i) => {
      const oscillator = context.createOscillator()
      const gain = context.createGain()
      oscillator.frequency.value = frequency
      gain.gain.setValueAtTime(0.0001, context.currentTime + i * 0.18)
      gain.gain.exponentialRampToValueAtTime(0.25, context.currentTime + i * 0.18 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + i * 0.18 + 0.3)
      oscillator.connect(gain).connect(context.destination)
      oscillator.start(context.currentTime + i * 0.18)
      oscillator.stop(context.currentTime + i * 0.18 + 0.32)
    })
  } catch {
    /* audio blocked by the browser: the visual alert still shows */
  }
}
