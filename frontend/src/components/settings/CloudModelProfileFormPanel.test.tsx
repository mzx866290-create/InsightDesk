import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { TranslationKey } from '../../i18n'
import type { CloudModelProfile } from '../../stores/chatStore'
import {
  CloudModelProfileFormPanel,
  type CloudModelProfileFormPanelProps,
} from './CloudModelProfileFormPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => (
    <button {...props}>{children}</button>
  ),
}))

const managedProfile: CloudModelProfile = {
  id: 'profile-1',
  name: 'Prod OpenRouter',
  modelConfig: {
    panel_id: 'profile-1',
    connection_type: 'openai_compatible',
    provider: 'openai_compatible',
    model: 'openai/gpt-4.1',
    base_url: 'https://openrouter.ai/api/v1',
    api_key: '',
    api_key_ref: 'managed-key-ref',
    temperature: 0.3,
    agent_mode: 'auto',
  },
  createdAt: 1,
  updatedAt: 2,
}

const t = (key: TranslationKey) => key

function createProps(overrides: Partial<CloudModelProfileFormPanelProps> = {}): CloudModelProfileFormPanelProps {
  return {
    form: {
      name: '',
      model: 'openai/gpt-4o-mini',
      baseUrl: 'https://openrouter.ai/api/v1',
      apiKey: '',
      temperature: 0.3,
    },
    editingProfile: null,
    editingProfileId: null,
    canSave: false,
    saving: false,
    apiKeyDeletingId: null,
    saveError: null,
    t,
    onChange: vi.fn(),
    onSave: vi.fn(),
    onReset: vi.fn(),
    onClearApiKey: vi.fn(),
    ...overrides,
  }
}

describe('CloudModelProfileFormPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards form input changes', () => {
    const onChange = vi.fn()

    render(<CloudModelProfileFormPanel {...createProps({ onChange })} />)

    fireEvent.change(screen.getByTestId('settings-cloud-profile-name-input'), {
      target: { value: 'Prod' },
    })
    fireEvent.change(screen.getByTestId('settings-cloud-profile-model-input'), {
      target: { value: 'openai/gpt-4.1' },
    })
    fireEvent.change(screen.getByTestId('settings-cloud-profile-base-url-input'), {
      target: { value: 'https://api.example.test/v1' },
    })
    fireEvent.change(screen.getByTestId('settings-cloud-profile-api-key-input'), {
      target: { value: 'sk-test' },
    })
    fireEvent.change(screen.getByDisplayValue('0.3'), {
      target: { value: '0.7' },
    })

    expect(onChange).toHaveBeenCalledWith({ name: 'Prod' })
    expect(onChange).toHaveBeenCalledWith({ model: 'openai/gpt-4.1' })
    expect(onChange).toHaveBeenCalledWith({ baseUrl: 'https://api.example.test/v1' })
    expect(onChange).toHaveBeenCalledWith({ apiKey: 'sk-test' })
    expect(onChange).toHaveBeenCalledWith({ temperature: 0.7 })
  })

  it('disables save while invalid or saving and forwards save when enabled', () => {
    const onSave = vi.fn()
    const { rerender } = render(
      <CloudModelProfileFormPanel
        {...createProps({
          canSave: false,
          onSave,
        })}
      />,
    )

    expect(screen.getByTestId('settings-cloud-profile-save')).toBeDisabled()

    rerender(
      <CloudModelProfileFormPanel
        {...createProps({
          canSave: true,
          saving: true,
          onSave,
        })}
      />,
    )
    expect(screen.getByTestId('settings-cloud-profile-save')).toBeDisabled()
    expect(screen.getByTestId('settings-cloud-profile-save')).toHaveTextContent('settings.cloud.saving')

    rerender(
      <CloudModelProfileFormPanel
        {...createProps({
          canSave: true,
          onSave,
        })}
      />,
    )
    fireEvent.click(screen.getByTestId('settings-cloud-profile-save'))

    expect(onSave).toHaveBeenCalledTimes(1)
  })

  it('renders edit state and forwards reset and managed key clearing', () => {
    const onReset = vi.fn()
    const onClearApiKey = vi.fn()

    render(
      <CloudModelProfileFormPanel
        {...createProps({
          editingProfile: managedProfile,
          editingProfileId: managedProfile.id,
          canSave: true,
          onReset,
          onClearApiKey,
        })}
      />,
    )

    expect(screen.getByTestId('settings-cloud-profile-save')).toHaveTextContent('settings.cloud.update')
    expect(screen.getByText('settings.cloud.currentKeyManaged')).toBeInTheDocument()

    fireEvent.click(screen.getByText('settings.cloud.resetForm'))
    fireEvent.click(screen.getByTestId('settings-cloud-profile-clear-editor'))

    expect(onReset).toHaveBeenCalledTimes(1)
    expect(onClearApiKey).toHaveBeenCalledWith(managedProfile)
  })

  it('shows save errors', () => {
    render(<CloudModelProfileFormPanel {...createProps({ saveError: 'Failed to save' })} />)

    expect(screen.getByText('Failed to save')).toBeInTheDocument()
  })
})
