import { useEffect, useState, type ReactNode } from 'react'
import { setAuthToken } from '../api/client'
import { AuthContext, type AuthState } from './auth-context'
import kc, { initializeKeycloak } from './keycloak'

const DEV_USER = {
  token: 'dev-token',
  username: 'advisor@laruche.local',
  roles: ['advisor'],
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const devAuth = import.meta.env.VITE_DEV_AUTH === 'true'

  const devSignedOut = window.sessionStorage.getItem('laruche-dev-signed-out') === 'true'

  const [state, setState] = useState<AuthState>({
    ready: devAuth,
    authenticated: devAuth && !devSignedOut,
    token: devAuth && !devSignedOut ? DEV_USER.token : null,
    username: devAuth && !devSignedOut ? DEV_USER.username : null,
    roles: devAuth && !devSignedOut ? DEV_USER.roles : [],
    login: () => {},
    logout: () => {},
  })

  const login = () => {
    if (devAuth) {
      window.sessionStorage.removeItem('laruche-dev-signed-out')
      setState(current => ({
        ...current,
        ready: true,
        authenticated: true,
        token: DEV_USER.token,
        username: DEV_USER.username,
        roles: DEV_USER.roles,
      }))
      return
    }

    void kc.login()
  }

  const logout = () => {
    setAuthToken(null)
    if (devAuth) {
      window.sessionStorage.setItem('laruche-dev-signed-out', 'true')
      setState(current => ({
        ...current,
        ready: true,
        authenticated: false,
        token: null,
        username: null,
        roles: [],
      }))
      return
    }

    setState(current => ({
      ...current,
      authenticated: false,
      token: null,
      username: null,
      roles: [],
    }))
    void kc.logout({ redirectUri: window.location.origin })
  }

  useEffect(() => {
    if (devAuth) return

    let active = true
    initializeKeycloak()
      .then(auth => {
        if (!active) return
        setState(current => ({
          ...current,
          ready: true,
          authenticated: auth,
          token: kc.token ?? null,
          username: kc.tokenParsed?.preferred_username ?? null,
          roles: (kc.tokenParsed?.realm_access?.roles as string[]) ?? [],
        }))
      })
      .catch(() => {
        if (!active) return
        setState(current => ({
          ...current,
          ready: true,
          authenticated: false,
          token: null,
          username: null,
          roles: [],
        }))
      })

    const interval = window.setInterval(() => {
      kc.updateToken(60).then(refreshed => {
        if (active && refreshed) {
          setState(current => ({ ...current, token: kc.token ?? null }))
        }
      })
    }, 60_000)

    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [devAuth])

  useEffect(() => {
    setAuthToken(state.token)
  }, [state.token])

  return <AuthContext.Provider value={{ ...state, login, logout }}>{children}</AuthContext.Provider>
}
