import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, clearSession, loginRequest, saveSession, sessionStorageKeys } from '../lib/api'
import type { User } from '../types/api'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!localStorage.getItem(sessionStorageKeys.access)) {
      setLoading(false)
      return
    }
    api<User>('/auth/me')
      .then(setUser)
      .catch(() => clearSession())
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login: async (email, password) => {
        const tokens = await loginRequest(email, password)
        saveSession(tokens)
        setUser(await api<User>('/auth/me'))
      },
      logout: async () => {
        const refreshToken = localStorage.getItem(sessionStorageKeys.refresh)
        if (refreshToken) {
          await api<void>('/auth/logout', {
            method: 'POST',
            body: JSON.stringify({ refresh_token: refreshToken }),
          }).catch(() => undefined)
        }
        clearSession()
        setUser(null)
      },
    }),
    [loading, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe utilizarse dentro de AuthProvider')
  return context
}
