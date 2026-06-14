import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import kc from './keycloak'

interface AuthState {
  ready: boolean
  authenticated: boolean
  token: string | null
  username: string | null
  roles: string[]
  login: () => void
  logout: () => void
}

const AuthContext = createContext<AuthState>({
  ready: false,
  authenticated: false,
  token: null,
  username: null,
  roles: [],
  login: () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    ready: false,
    authenticated: false,
    token: null,
    username: null,
    roles: [],
    login: () => kc.login(),
    logout: () => kc.logout(),
  })

  useEffect(() => {
    // Dev bypass — no Keycloak needed when VITE_DEV_AUTH=true
    if (import.meta.env.VITE_DEV_AUTH === 'true') {
      setState(s => ({
        ...s,
        ready: true,
        authenticated: true,
        token: 'dev-token',
        username: 'advisor@wealthmesh.local',
        roles: ['advisor'],
      }))
      return
    }

    kc.init({ onLoad: 'check-sso', pkceMethod: 'S256' }).then(auth => {
      setState(s => ({
        ...s,
        ready: true,
        authenticated: auth,
        token: kc.token ?? null,
        username: kc.tokenParsed?.preferred_username ?? null,
        roles: (kc.tokenParsed?.realm_access?.roles as string[]) ?? [],
      }))
    })

    // Refresh token every 60s
    const interval = setInterval(() => {
      kc.updateToken(60).then(refreshed => {
        if (refreshed) {
          setState(s => ({ ...s, token: kc.token ?? null }))
        }
      })
    }, 60_000)
    return () => clearInterval(interval)
  }, [])

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
