import { create } from 'zustand'
import { logoutApi, verifyApi } from '../api/auth'
import { AUTH_TOKEN_STORAGE_KEY } from '../api/client'

type AuthStore = {
  token: string | null
  isAuthenticated: boolean
  hydrate: () => Promise<void>
  login: (token: string) => void
  logout: () => Promise<void>
  verifyToken: () => Promise<boolean>
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function persistToken(token: string) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token)
}

function clearPersistedToken() {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
}

function getPersistedToken() {
  if (!canUseStorage()) {
    return null
  }

  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
}

function redirectToLogin() {
  if (typeof window === 'undefined' || window.location.pathname === '/login') {
    return
  }

  window.history.replaceState({}, '', '/login')
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function clearAuthState() {
  clearPersistedToken()
  useAuthStore.setState({
    isAuthenticated: false,
    token: null,
  })
}

export function handleUnauthorized() {
  clearAuthState()
  redirectToLogin()
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: null,
  isAuthenticated: false,
  hydrate: async () => {
    const storedToken = getPersistedToken()

    if (!storedToken) {
      clearAuthState()
      return
    }

    set({
      isAuthenticated: false,
      token: storedToken,
    })

    const verified = await get().verifyToken()

    if (!verified) {
      redirectToLogin()
    }
  },
  login: (token) => {
    persistToken(token)
    set({
      isAuthenticated: true,
      token,
    })
  },
  logout: async () => {
    try {
      if (get().token) {
        await logoutApi()
      }
    } finally {
      handleUnauthorized()
    }
  },
  verifyToken: async () => {
    const token = get().token ?? getPersistedToken()

    if (!token) {
      clearAuthState()
      return false
    }

    try {
      await verifyApi()
      persistToken(token)
      set({
        isAuthenticated: true,
        token,
      })
      return true
    } catch {
      clearAuthState()
      return false
    }
  },
}))
