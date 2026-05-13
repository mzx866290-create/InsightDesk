import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useChatStore } from '../../stores/chatStore'
import { TavilySettingsPanel } from './TavilySettingsPanel'

describe('TavilySettingsPanel', () => {
  const defaultProps = {
    tavilyKey: '',
    tavilyKeySet: false,
    saving: false,
    saveOk: false,
    saveError: null,
    onTavilyKeyChange: vi.fn(),
    onSaveGeneral: vi.fn(),
    onClearTavilyKey: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    useChatStore.setState({ language: 'en-US' })
  })

  afterEach(() => {
    cleanup()
  })

  it('keeps input and save behavior wired to the existing props', () => {
    render(<TavilySettingsPanel {...defaultProps} />)

    fireEvent.change(screen.getByTestId('settings-tavily-key-input'), {
      target: { value: 'tvly-test-key' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }))

    expect(defaultProps.onTavilyKeyChange).toHaveBeenCalledWith('tvly-test-key')
    expect(defaultProps.onSaveGeneral).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: 'Clear Tavily Key' })).not.toBeInTheDocument()
  })

  it('shows configured status, clear action, saved state, and save errors', () => {
    render(
      <TavilySettingsPanel
        {...defaultProps}
        tavilyKeySet
        saveOk
        saveError="Unable to save Tavily key"
      />,
    )

    expect(screen.getByText('Configured')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Configured; leave blank to keep current value')).toBeInTheDocument()
    expect(screen.getByText('Unable to save Tavily key')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Clear Tavily Key' }))

    expect(defaultProps.onClearTavilyKey).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Saved' })).toBeInTheDocument()
  })
})
