import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpConfigResponse } from '../../api/client'
import { McpConfigSection } from './McpConfigSection'

const config = (patch: Partial<McpConfigResponse> = {}): McpConfigResponse => ({
  config: {},
  connectors: [],
  servers: {},
  default_enabled: [],
  persistence: { enabled: true, config_key: 'mcp.runtime.config' },
  source: 'runtime',
  sensitive_fields_redacted: false,
  ...patch,
})

function renderSection(overrides: Partial<React.ComponentProps<typeof McpConfigSection>> = {}) {
  const props: React.ComponentProps<typeof McpConfigSection> = {
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
    ...render(<McpConfigSection {...props} />),
  }
}

describe('McpConfigSection', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards config metadata and editor actions', () => {
    const onValueChange = vi.fn()
    const onSave = vi.fn()

    renderSection({
      config: config({ sensitive_fields_redacted: true }),
      onValueChange,
      onSave,
    })

    expect(screen.getByTestId('settings-mcp-config-panel')).toHaveTextContent('mcp.runtime.config')
    expect(screen.getByText('redacted')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('settings-mcp-config-editor'), {
      target: { value: '{"default_enabled":["kb"]}' },
    })
    fireEvent.click(screen.getByTestId('settings-mcp-config-save'))

    expect(onValueChange).toHaveBeenCalledWith('{"default_enabled":["kb"]}')
    expect(onSave).toHaveBeenCalledTimes(1)
  })
})
