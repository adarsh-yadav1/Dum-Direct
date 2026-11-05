/**
 * Base URL of the API. By default the app calls /api on its own address, in development
 * through the Vite proxy and in production because the server serves both. One address keeps
 * the sign-in cookie first-party. Set VITE_API_BASE_URL only to reach an API elsewhere.
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  readonly status: number
  /** The API's machine-readable code when it sent one, such as "items_unavailable". */
  readonly code: string | null
  readonly itemIds: number[]

  constructor(message: string, status: number, code: string | null = null, itemIds: number[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.itemIds = itemIds
  }
}

type ErrorBody = {
  detail?: string | { code?: string; message?: string; item_ids?: number[] } | { msg?: string }[]
}

function describe(body: ErrorBody | null, status: number): ApiError {
  const detail = body?.detail
  if (typeof detail === 'string') return new ApiError(detail, status)
  if (Array.isArray(detail)) return new ApiError('Some of the details are not valid. Check them and try again.', status)
  if (detail && typeof detail === 'object') {
    const d = detail as { code?: string; message?: string; item_ids?: number[] }
    return new ApiError(d.message ?? 'Something went wrong. Try again.', status, d.code ?? null, d.item_ids ?? [])
  }
  return new ApiError(status >= 500 ? 'The server had a problem. Try again in a moment.' : 'Something went wrong. Try again.', status)
}

/** Small typed wrapper over fetch. Sends cookies, so sessions work. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: 'include',
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0)
  }

  if (!response.ok) {
    let body: ErrorBody | null = null
    try {
      body = (await response.json()) as ErrorBody
    } catch {
      /* not JSON */
    }
    throw describe(body, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function post<T>(path: string, body: unknown, headers: Record<string, string> = {}): Promise<T> {
  return api<T>(path, { method: 'POST', body: JSON.stringify(body), headers })
}
