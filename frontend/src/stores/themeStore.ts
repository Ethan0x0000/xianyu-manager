import { create } from 'zustand'

export const DEFAULT_THEME_COLOR = '#1890ff'

const DARK_MODE_STORAGE_KEY = 'darkMode'
const THEME_COLOR_STORAGE_KEY = 'themeColor'
const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/

type ThemeStore = {
  darkMode: boolean
  themeColor: string
  toggleDark: () => void
  setThemeColor: (color: string) => void
  hydrate: () => void
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function normalizeThemeColor(color: string | null) {
  return color && HEX_COLOR_PATTERN.test(color) ? color : DEFAULT_THEME_COLOR
}

function persistDarkMode(darkMode: boolean) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(DARK_MODE_STORAGE_KEY, String(darkMode))
}

function persistThemeColor(themeColor: string) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(THEME_COLOR_STORAGE_KEY, themeColor)
}

export const useThemeStore = create<ThemeStore>((set) => ({
  darkMode: false,
  themeColor: DEFAULT_THEME_COLOR,
  toggleDark: () => {
    set((state) => {
      const nextDarkMode = !state.darkMode
      persistDarkMode(nextDarkMode)

      return { darkMode: nextDarkMode }
    })
  },
  setThemeColor: (color) => {
    const nextThemeColor = normalizeThemeColor(color)
    persistThemeColor(nextThemeColor)
    set({ themeColor: nextThemeColor })
  },
  hydrate: () => {
    if (!canUseStorage()) {
      return
    }

    const storedDarkMode = window.localStorage.getItem(DARK_MODE_STORAGE_KEY) === 'true'
    const storedThemeColor = normalizeThemeColor(window.localStorage.getItem(THEME_COLOR_STORAGE_KEY))

    persistDarkMode(storedDarkMode)
    persistThemeColor(storedThemeColor)

    set((state) => {
      if (
        state.darkMode === storedDarkMode &&
        state.themeColor === storedThemeColor
      ) {
        return state
      }

      return {
        darkMode: storedDarkMode,
        themeColor: storedThemeColor,
      }
    })
  },
}))
