import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { SsoConfig } from '../../api/client'
import type { TranslationKey } from '../../i18n'
import { SsoConfigSummaryPanel } from './SsoConfigSummaryPanel'

const t = (key: TranslationKey) => key

const baseSsoConfig: SsoConfig = {
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
  allowed_domains: ['example.com', 'admin.example.com'],
  scopes: ['openid', 'email', 'profile'],
  default_role: 'viewer',
  session_ttl_seconds: 28800,
  callback_path: '/auth/sso/callback',
  ready: true,
  mode: 'strict',
  claim_mapping: { email: 'email' },
}

describe('SsoConfigSummaryPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders configured summary values and allowed domains', () => {
    render(<SsoConfigSummaryPanel config={baseSsoConfig} t={t} />)

    expect(screen.getByText(/settings\.sso\.summaryProvider:/)).toHaveTextContent('oidc')
    expect(screen.getByText(/settings\.sso\.summaryMode:/)).toHaveTextContent('strict')
    expect(screen.getByText(/settings\.sso\.summaryAuthUrl:/)).toHaveTextContent('settings.sso.summarySet')
    expect(screen.getByText(/settings\.sso\.summaryJwks:/)).toHaveTextContent('settings.sso.summarySet')
    expect(screen.getByText(/settings\.sso\.summaryAllowedDomains:/)).toHaveTextContent(
      'example.com, admin.example.com',
    )
  })

  it('renders missing summary values and hides empty allowed domains', () => {
    render(
      <SsoConfigSummaryPanel
        config={{
          ...baseSsoConfig,
          provider: 'none',
          mode: 'disabled',
          authorization_endpoint_configured: false,
          jwks_url_configured: false,
          allowed_domains: [],
        }}
        t={t}
      />,
    )

    expect(screen.getByText(/settings\.sso\.summaryProvider:/)).toHaveTextContent('none')
    expect(screen.getByText(/settings\.sso\.summaryMode:/)).toHaveTextContent('disabled')
    expect(screen.getByText(/settings\.sso\.summaryAuthUrl:/)).toHaveTextContent('settings.sso.summaryMissing')
    expect(screen.getByText(/settings\.sso\.summaryJwks:/)).toHaveTextContent('settings.sso.summaryMissing')
    expect(screen.queryByText(/settings\.sso\.summaryAllowedDomains:/)).not.toBeInTheDocument()
  })

  it('renders empty placeholders before config loads', () => {
    render(<SsoConfigSummaryPanel config={null} t={t} />)

    expect(screen.getByText(/settings\.sso\.summaryProvider:/)).toHaveTextContent('-')
    expect(screen.getByText(/settings\.sso\.summaryMode:/)).toHaveTextContent('-')
    expect(screen.getByText(/settings\.sso\.summaryAuthUrl:/)).toHaveTextContent('settings.sso.summaryMissing')
    expect(screen.getByText(/settings\.sso\.summaryJwks:/)).toHaveTextContent('settings.sso.summaryMissing')
  })
})
