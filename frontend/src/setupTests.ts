import '@testing-library/jest-dom'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const originalConsoleError = console.error

console.error = (...args: unknown[]) => {
  const [firstArg] = args

  if (typeof firstArg === 'string' && firstArg.includes('not wrapped in act(...)')) {
    return
  }

  originalConsoleError(...args)
}

const originalGetComputedStyle = window.getComputedStyle.bind(window)

window.getComputedStyle = ((element: Element, pseudoElt?: string) => {
  if (pseudoElt) {
    return originalGetComputedStyle(element)
  }

  return originalGetComputedStyle(element)
}) as typeof window.getComputedStyle

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    addListener: () => undefined,
    dispatchEvent: () => false,
    removeEventListener: () => undefined,
    removeListener: () => undefined,
  }),
})
