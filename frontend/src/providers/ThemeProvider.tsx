import { useRef, type ReactNode } from 'react'
import { ConfigProvider, theme as antdTheme } from 'antd'
import { useThemeStore } from '../stores/themeStore'

type ThemeProviderProps = {
  children: ReactNode
}

export default function ThemeProvider({ children }: ThemeProviderProps) {
  const hydratedRef = useRef(false)

  if (!hydratedRef.current) {
    useThemeStore.getState().hydrate()
    hydratedRef.current = true
  }

  const darkMode = useThemeStore((state) => state.darkMode)
  const themeColor = useThemeStore((state) => state.themeColor)
  const algorithm = darkMode ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm

  return (
    <ConfigProvider
      theme={{
        algorithm,
        token: {
          colorPrimary: themeColor,
        },
      }}
    >
      {children}
    </ConfigProvider>
  )
}
