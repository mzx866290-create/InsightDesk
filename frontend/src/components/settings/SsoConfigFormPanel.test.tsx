import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SsoConfig } from '../../api/client'
import type { TranslationKey } from '../../i18n'
import { DEFAULT_SSO_FORM } from './ssoSettingsModel'
import { SsoConfigFormPanel, type SsoConfigFormPanelProps } from './SsoConfigFormPanel'

const t = (key: TranslationKey) => key

const configuredSsoConfig: SsoConfig = {
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

function createProps(overrides: Partial<SsoConfigFormPanelProps> = {}): SsoConfigFormPanelProps {
  return {
    config: configuredSsoConfig,
    form: DEFAULT_SSO_FORM,
    t,
    onFormChange: vi.fn(),
    ...overrides,
  }
}

describe('SsoConfigFormPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards form input changes', () => {
    const onFormChange = vi.fn()

    render(<SsoConfigFormPanel {...createProps({ onFormChange })} />)

    fireEvent.change(screen.getByTestId('settings-sso-provider-input'), {
      target: { value: 'oidc' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-default-role-input'), {
      target: { value: 'admin' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-issuer-url-input'), {
      target: { value: 'https://issuer.example.com' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-authorization-endpoint-input'), {
      target: { value: 'https://issuer.example.com/authorize' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-token-endpoint-input'), {
      target: { value: 'https://issuer.example.com/token' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-jwks-url-input'), {
      target: { value: 'https://issuer.example.com/jwks' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-client-id-input'), {
      target: { value: 'dashboard-web' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-client-secret-input'), {
      target: { value: 'secret-value' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-scopes-input'), {
      target: { value: 'openid email' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-session-ttl-input'), {
      target: { value: '7200' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-allowed-domains-input'), {
      target: { value: 'example.com, admin.example.com' },
    })

    expect(onFormChange).toHaveBeenCalledWith('provider', 'oidc')
    expect(onFormChange).toHaveBeenCalledWith('default_role', 'admin')
    expect(onFormChange).toHaveBeenCalledWith('issuer_url', 'https://issuer.example.com')
    expect(onFormChange).toHaveBeenCalledWith('authorization_endpoint', 'https://issuer.example.com/authorize')
    expect(onFormChange).toHaveBeenCalledWith('token_endpoint', 'https://issuer.example.com/token')
    expect(onFormChange).toHaveBeenCalledWith('jwks_url', 'https://issuer.example.com/jwks')
    expect(onFormChange).toHaveBeenCalledWith('client_id', 'dashboard-web')
    expect(onFormChange).toHaveBeenCalledWith('client_secret', 'secret-value')
    expect(onFormChange).toHaveBeenCalledWith('scopes', 'openid email')
    expect(onFormChange).toHaveBeenCalledWith('session_ttl_seconds', 7200)
    expect(onFormChange).toHaveBeenCalledWith('allowed_domains', 'example.com, admin.example.com')
  })

  it('forwards disabled provider and empty ttl fallback values', () => {
    const onFormChange = vi.fn()

    render(
      <SsoConfigFormPanel
        {...createProps({
          form: { ...DEFAULT_SSO_FORM, provider: 'oidc' },
          onFormChange,
        })}
      />,
    )

    fireEvent.change(screen.getByTestId('settings-sso-provider-input'), {
      target: { value: 'none' },
    })
    fireEvent.change(screen.getByTestId('settings-sso-session-ttl-input'), {
      target: { value: '' },
    })

    expect(onFormChange).toHaveBeenCalledWith('provider', 'none')
    expect(onFormChange).toHaveBeenCalledWith('session_ttl_seconds', 28800)
  })

  it('forwards the secret clear checkbox and keeps configured placeholder behavior', () => {
    const onFormChange = vi.fn()

    render(
      <SsoConfigFormPanel
        {...createProps({
          form: { ...DEFAULT_SSO_FORM, clear_client_secret: true },
          onFormChange,
        })}
      />,
    )

    expect(screen.getByTestId('settings-sso-client-secret-input')).toHaveAttribute(
      'placeholder',
      'settings.sso.clientSecretConfiguredPlaceholder',
    )
    expect(screen.getByTestId('settings-sso-clear-client-secret-input')).toBeChecked()

    fireEvent.click(screen.getByTestId('settings-sso-clear-client-secret-input'))

    expect(onFormChange).toHaveBeenCalledWith('clear_client_secret', false)
  })
})
