import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SsoConfig } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { DEFAULT_SSO_FORM } from './ssoSettingsModel'
import { SsoSettingsPanel, type SsoSettingsPanelProps } from './SsoSettingsPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading = false,
    variant: _variant,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
  }) => (
    <button {...props} disabled={props.disabled || loading} data-loading={loading ? 'true' : 'false'}>
      {children}
    </button>
  ),
}))

const readySsoConfig: SsoConfig = {
  enabled: true,
  provider: 'oidc',
  issuer_url: 'https://issuer.example.com',
  authorization_endpoint: 'https://issuer.example.com/authorize',
  token_endpoint: 'https://issuer.example.com/token',
  jwks_url: 'https://issuer.example.com/.well-known/jwks.json',
  authorization_endpoint_configured: true,
  token_endpoint_configured: true,
  jwks_url_configured: true,
  client_id: 'dashboard-web',
  client_id_configured: true,
  client_secret_configured: true,
  allowed_domains: ['example.com'],
  scopes: ['openid', 'email', 'profile'],
  default_role: 'viewer',
  session_ttl_seconds: 28800,
  callback_path: '/auth/sso/callback',
  ready: true,
  mode: 'strict',
  claim_mapping: { email: 'email' },
}

function createProps(overrides: Partial<SsoSettingsPanelProps> = {}): SsoSettingsPanelProps {
  return {
    config: readySsoConfig,
    form: DEFAULT_SSO_FORM,
    loading: false,
    saving: false,
    loginStarting: false,
    error: null,
    onFormChange: vi.fn(),
    onSave: vi.fn(),
    onStartLogin: vi.fn(),
    onRefresh: vi.fn(),
    ...overrides,
  }
}

describe('SsoSettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useChatStore.setState({ language: 'en-US' })
  })

  afterEach(() => {
    cleanup()
  })

  it('keeps top-level actions wired and enables login only when config is ready', () => {
    const props = createProps()

    render(<SsoSettingsPanel {...props} />)

    fireEvent.click(screen.getByTestId('settings-sso-save'))
    fireEvent.click(screen.getByTestId('settings-sso-login'))
    fireEvent.click(screen.getByTestId('settings-sso-refresh'))

    expect(props.onSave).toHaveBeenCalledTimes(1)
    expect(props.onStartLogin).toHaveBeenCalledTimes(1)
    expect(props.onRefresh).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('settings-sso-login')).not.toBeDisabled()
  })

  it('reflects loading states and disables login when SSO is not ready', () => {
    render(
      <SsoSettingsPanel
        {...createProps({
          config: { ...readySsoConfig, ready: false },
          loading: true,
          saving: true,
          loginStarting: true,
          error: 'Unable to save SSO settings',
        })}
      />,
    )

    expect(screen.getByTestId('settings-sso-status')).toHaveTextContent('Checking')
    expect(screen.getByTestId('settings-sso-save')).toBeDisabled()
    expect(screen.getByTestId('settings-sso-save')).toHaveAttribute('data-loading', 'true')
    expect(screen.getByTestId('settings-sso-login')).toBeDisabled()
    expect(screen.getByTestId('settings-sso-login')).toHaveAttribute('data-loading', 'true')
    expect(screen.getByTestId('settings-sso-refresh')).toBeDisabled()
    expect(screen.getByTestId('settings-sso-refresh')).toHaveAttribute('data-loading', 'true')
    expect(screen.getByTestId('settings-sso-error')).toHaveTextContent('Unable to save SSO settings')
  })
})
