import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import Sidebar from './Sidebar'

describe('Sidebar', () => {
  it('renders branding and key navigation links', () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    )

    expect(screen.getByText('QA Insight AI')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Test Runs' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument()
  })

  it('renders AI agent section links', () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    )

    expect(screen.getByText('AI Agents')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AI Pipeline' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Deep Analysis' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Release Gate' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Chat' })).toBeInTheDocument()
  })
})
