import { createContext, useContext } from 'react'
import type { SignupInput, User } from './api'

export interface AuthState {
  user: User | null
  ready: boolean // false until we've asked the backend who is logged in
  login: (email: string, password: string) => Promise<User>
  signup: (input: SignupInput) => Promise<User>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
