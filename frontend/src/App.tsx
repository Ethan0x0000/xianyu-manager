import { useEffect, useRef, type ReactNode } from 'react'
import { BrowserRouter } from 'react-router-dom'
import RouterOutlet from './router'
import QueryProvider from './providers/QueryProvider'
import ThemeProvider from './providers/ThemeProvider'
import { useAuthStore } from './stores/authStore'

type AuthBootstrapProps = {
  children: ReactNode
}

function AuthBootstrap({ children }: AuthBootstrapProps) {
  const hydrate = useAuthStore((state) => state.hydrate)
  const hydratedRef = useRef(false)

  useEffect(() => {
    if (hydratedRef.current) {
      return
    }

    hydratedRef.current = true
    void hydrate()
  }, [hydrate])

  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter
      future={{
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      }}
    >
      <QueryProvider>
        <ThemeProvider>
          <AuthBootstrap>
            <RouterOutlet />
          </AuthBootstrap>
        </ThemeProvider>
      </QueryProvider>
    </BrowserRouter>
  )
}

export default App
