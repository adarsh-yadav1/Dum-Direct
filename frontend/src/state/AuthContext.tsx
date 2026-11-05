import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, post } from '../lib/api'
import type { User } from '../lib/types'

type RegisterInput = { name: string; email: string; password: string; phone?: string; marketing_opt_in: boolean }

type AuthValue = {
  user: User | null
  /** True until the first check of the session has finished. */
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (input: RegisterInput) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api<User>('/auth/me')
      .then((u) => !cancelled && setUser(u))
      .catch(() => !cancelled && setUser(null))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const u = await post<User>('/auth/login', { email, password })
    setUser(u)
    return u
  }, [])

  const register = useCallback(async (input: RegisterInput) => {
    const body = { ...input, phone: input.phone?.trim() || null }
    const u = await post<User>('/auth/register', body)
    setUser(u)
    return u
  }, [])

  const logout = useCallback(async () => {
    await post<void>('/auth/logout', {})
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
