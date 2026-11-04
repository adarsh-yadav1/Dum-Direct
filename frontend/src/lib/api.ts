/**
 * Base URL of the API. By default the app calls /api on its own address, in development
 * through the Vite proxy and in production because the server serves both. One address keeps
 * the sign-in cookie first-party. Set VITE_API_BASE_URL only to reach an API elsewhere.
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Small typed wrapper over fetch. Sends cookies, so sessions work across origins. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
    ...init,
  })

  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, response.status)
  }
  return (await response.json()) as T
}
