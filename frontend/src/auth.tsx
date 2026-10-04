import { useEffect, useState, type ReactNode } from 'react'
import * as api from './api'
import type { User } from './api'
import { AuthContext, type AuthState } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  // On page load, restore the session from the HttpOnly cookie (if any).
  useEffect(() => {
    api
      .fetchCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  const value: AuthState = {
    user,
    ready,
    login: async (email, password) => {
      const u = await api.login(email, password)
      setUser(u)
      return u
    },
    signup: async (input) => {
      const u = await api.signup(input)
      setUser(u)
      return u
    },
    logout: async () => {
      await api.logout()
      setUser(null)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

