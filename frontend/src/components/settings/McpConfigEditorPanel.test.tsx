import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpConfigResponse } from '../../api/client'
import { McpConfigEditorPanel } from './McpConfigEditorPanel'

const config = (patch: Partial<McpConfigResponse> = {}): McpConfigResponse => ({
  config: {},
  connectors: [],
  servers: {},
  default_enabled: [],
  persistence: { enabled: true, config_key: 'mcp.runtime.config' },
  source: 'runtime',
  sensitive_fields_redacted: true,
  ...patch,
})

function renderPanel(overrides: Partial<React.ComponentProps<typeof McpConfigEditorPanel>> = {}) {
  const props: React.ComponentProps<typeof McpConfigEditorPanel> = {
    config: config(),
    value: '{\n  "connectors": []\n}',
    loading: false,
    saving: false,
    onValueChange: vi.fn(),
    onSave: vi.fn(),
    ...overrides,
  }

  return {
    props,
    ...render(<McpConfigEditorPanel {...props} />),
  }
}

describe('McpConfigEditorPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders config persistence metadata and redaction status', () => {
    renderPanel()

    expect(screen.getByTestId('settings-mcp-config-panel')).toHaveTextContent('Config')
    expect(screen.getByText('mcp.runtime.config')).toBeInTheDocument()
    expect(screen.getByText('redacted')).toBeInTheDocument()
  })

  it('emits editor changes and save action', () => {
    const onValueChange = vi.fn()
    const onSave = vi.fn()

    renderPanel({ onValueChange, onSave })

    fireEvent.change(screen.getByTestId('settings-mcp-config-editor'), {
      target: { value: '{"default_enabled":true}' },
    })
    fireEvent.click(screen.getByTestId('settings-mcp-config-save'))

    expect(onValueChange).toHaveBeenCalledWith('{"default_enabled":true}')
    expect(onSave).toHaveBeenCalledTimes(1)
  })

  it('disables editor actions while loading or when value is blank', () => {
    const { rerender, props } = renderPanel({ loading: true })

    expect(screen.getByTestId('settings-mcp-config-editor')).toBeDisabled()
    expect(screen.getByTestId('settings-mcp-config-save')).toBeDisabled()

    rerender(<McpConfigEditorPanel {...props} loading={false} value="   " />)

    expect(screen.getByTestId('settings-mcp-config-editor')).not.toBeDisabled()
    expect(screen.getByTestId('settings-mcp-config-save')).toBeDisabled()
  })
})
