import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('react-use-websocket', () => ({
  default: () => ({
    sendMessage: vi.fn(),
    sendJsonMessage: vi.fn(),
    readyState: 1
  }),
  ReadyState: {
    CONNECTING: 0,
    OPEN: 1,
    CLOSING: 2,
    CLOSED: 3
  }
}))

import App from './app'

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByText('Streamline')).toBeInTheDocument()
    expect(screen.getByText('Agent Streamline')).toBeInTheDocument()
  })
})
