import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the app title', () => {
    render(<App />)
    expect(screen.getByText('Xianyu Manager')).toBeInTheDocument()
  })

  it('renders welcome message', () => {
    render(<App />)
    expect(screen.getByText('Welcome to the Xianyu Manager application')).toBeInTheDocument()
  })
})
