import { create } from 'zustand'
import { logoutApi, verifyApi } from '../api/auth'

type AuthStore = {
  isAuthenticated: boolean
  isInitializing: boolean
  hydrate: () => Promise<void>
  logout: () => Promise<void>
  verifyToken: () => Promise<boolean>
}

function redirectToLogin() {
  if (typeof window === 'undefined' || window.location.pathname === '/login') {
    return
  }

  window.history.replaceState({}, '', '/login')
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function clearAuthState() {
  useAuthStore.setState({
    isAuthenticated: false,
    isInitializing: false,
  })
}

export function handleUnauthorized() {
  clearAuthState()
  redirectToLogin()
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  isAuthenticated: false,
  isInitializing: true,
  hydrate: async () => {
    set({
      isAuthenticated: false,
      isInitializing: true,
    })
    await get().verifyToken()
  },
  logout: async () => {
    try {
      await logoutApi()
    } finally {
      handleUnauthorized()
    }
  },
  verifyToken: async () => {
    set((state) => ({
      ...state,
      isInitializing: true,
    }))

    try {
      await verifyApi()
      set({
        isAuthenticated: true,
        isInitializing: false,
      })
      return true
    } catch {
      clearAuthState()
      return false
    }
  },
}))
