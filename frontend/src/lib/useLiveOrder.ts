import { useCallback, useEffect, useRef, useState } from 'react'

import { API_BASE_URL, api } from './api'
import { isFinal } from './orders'
import type { Order } from './types'

const POLL_MS = 15_000

/**
 * An order that keeps itself current. A live stream (Server-Sent Events) says when something
 * changed and the order is then re-read. Every 15 seconds it is also re-read on its own, so a
 * blocked or broken stream only costs a few seconds, never correctness.
 */
export function useLiveOrder(code: string) {
  const [order, setOrder] = useState<Order | null>(null)
  const [error, setError] = useState<string | null>(null)
  const cursor = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const next = await api<Order>(`/orders/${code}`)
      cursor.current ??= next.last_event_id
      setOrder(next)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [code])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const watching = order !== null && !isFinal(order.status)
  useEffect(() => {
    if (!watching) return
    const timer = window.setInterval(() => void refresh(), POLL_MS)
    let source: EventSource | null = null
    if (typeof EventSource !== 'undefined') {
      source = new EventSource(`${API_BASE_URL}/orders/${code}/stream?after=${cursor.current ?? 0}`, { withCredentials: true })
      source.onmessage = () => void refresh()
    }
    return () => {
      window.clearInterval(timer)
      source?.close()
    }
  }, [watching, code, refresh])

  return { order, error, setOrder, refresh }
}
