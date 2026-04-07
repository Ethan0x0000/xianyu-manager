import type { JSX } from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AppErrorBoundary from '../components/AppErrorBoundary'

function ThrowingChild(): JSX.Element {
  throw new Error('boom')
}

describe('AppErrorBoundary', () => {
  it('renders a fallback message when a child throws', () => {
    const originalError = console.error
    console.error = () => undefined

    try {
      render(
        <AppErrorBoundary>
          <ThrowingChild />
        </AppErrorBoundary>,
      )
    } finally {
      console.error = originalError
    }

    expect(screen.getByText('页面发生错误')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刷新页面' })).toBeInTheDocument()
  })
})
