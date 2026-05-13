import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { TranslationKey } from '../../i18n'
import type { CloudModelProfile } from '../../stores/chatStore'
import {
  CloudModelProfileListPanel,
  type CloudModelProfileListPanelProps,
} from './CloudModelProfileListPanel'

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

const unmanagedProfile: CloudModelProfile = {
  ...managedProfile,
  id: 'profile-2',
  name: 'Local Proxy',
  modelConfig: {
    ...managedProfile.modelConfig,
    panel_id: 'profile-2',
    model: 'local/model',
    api_key_ref: '',
  },
}

const t = (key: TranslationKey) => key

function createProps(overrides: Partial<CloudModelProfileListPanelProps> = {}): CloudModelProfileListPanelProps {
  return {
    profiles: [managedProfile, unmanagedProfile],
    saving: false,
    apiKeyDeletingId: null,
    t,
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onClearApiKey: vi.fn(),
    ...overrides,
  }
}

describe('CloudModelProfileListPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders the empty state', () => {
    render(<CloudModelProfileListPanel {...createProps({ profiles: [] })} />)

    expect(screen.getByText('settings.cloud.savedProfiles')).toBeInTheDocument()
    expect(screen.getByText('settings.cloud.empty')).toBeInTheDocument()
    expect(screen.queryByTestId('settings-cloud-profile-list')).not.toBeInTheDocument()
  })

  it('renders saved profiles with stable test ids and key status', () => {
    render(<CloudModelProfileListPanel {...createProps()} />)

    const cards = screen.getAllByTestId('settings-cloud-profile-card')
    expect(cards).toHaveLength(2)

    expect(cards[0]).toHaveAttribute('data-profile-id', 'profile-1')
    expect(cards[0]).toHaveAttribute('data-profile-name', 'Prod OpenRouter')
    expect(within(cards[0]).getByText('Prod OpenRouter')).toBeInTheDocument()
    expect(within(cards[0]).getByText('openai/gpt-4.1')).toBeInTheDocument()
    expect(within(cards[0]).getByText('https://openrouter.ai/api/v1')).toBeInTheDocument()
    expect(within(cards[0]).getByText('settings.cloud.keyManaged')).toBeInTheDocument()

    expect(cards[1]).toHaveAttribute('data-profile-id', 'profile-2')
    expect(cards[1]).toHaveAttribute('data-profile-name', 'Local Proxy')
    expect(within(cards[1]).getByText('settings.cloud.keyNotManaged')).toBeInTheDocument()
    expect(within(cards[1]).queryByTestId('settings-cloud-profile-clear')).not.toBeInTheDocument()
  })

  it('forwards edit, delete, and clear key callbacks', () => {
    const onEdit = vi.fn()
    const onDelete = vi.fn()
    const onClearApiKey = vi.fn()

    render(
      <CloudModelProfileListPanel
        {...createProps({
          onEdit,
          onDelete,
          onClearApiKey,
        })}
      />,
    )

    const firstCard = screen.getAllByTestId('settings-cloud-profile-card')[0]
    fireEvent.click(within(firstCard).getByTestId('settings-cloud-profile-edit'))
    fireEvent.click(within(firstCard).getByTestId('settings-cloud-profile-delete'))
    fireEvent.click(within(firstCard).getByTestId('settings-cloud-profile-clear'))

    expect(onEdit).toHaveBeenCalledWith(managedProfile)
    expect(onDelete).toHaveBeenCalledWith(managedProfile)
    expect(onClearApiKey).toHaveBeenCalledWith(managedProfile)
  })

  it('disables clear key while saving or clearing the same profile', () => {
    const { rerender } = render(<CloudModelProfileListPanel {...createProps({ saving: true })} />)

    expect(screen.getByTestId('settings-cloud-profile-clear')).toBeDisabled()

    rerender(
      <CloudModelProfileListPanel
        {...createProps({
          saving: false,
          apiKeyDeletingId: managedProfile.id,
        })}
      />,
    )

    expect(screen.getByTestId('settings-cloud-profile-clear')).toBeDisabled()
    expect(screen.getByTestId('settings-cloud-profile-clear')).toHaveTextContent('settings.cloud.clearingKey')
  })
})
