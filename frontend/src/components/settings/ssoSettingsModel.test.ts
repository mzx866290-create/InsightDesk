import { describe, expect, it } from 'vitest'

import type { SsoConfig } from '../../api/client'
import { DEFAULT_SSO_FORM, ssoConfigToForm } from './ssoSettingsModel'

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
  default_role: 'editor',
  session_ttl_seconds: 7200,
  callback_path: '/auth/sso/callback',
  ready: true,
  mode: 'strict',
  claim_mapping: { email: 'email' },
}

describe('ssoSettingsModel', () => {
  it('uses default form values when no config is loaded', () => {
    expect(ssoConfigToForm(null)).toEqual(DEFAULT_SSO_FORM)
  })

  it('serializes loaded config into editable form fields without exposing the client secret', () => {
    expect(ssoConfigToForm(baseSsoConfig)).toEqual({
      provider: 'oidc',
      issuer_url: 'https://issuer.example.com',
      authorization_endpoint: 'https://issuer.example.com/authorize',
      token_endpoint: 'https://issuer.example.com/token',
      jwks_url: 'https://issuer.example.com/.well-known/jwks.json',
      client_id: 'dashboard-web',
      client_secret: '',
      clear_client_secret: false,
      allowed_domains: 'example.com, admin.example.com',
      scopes: 'openid email profile',
      default_role: 'editor',
      session_ttl_seconds: 7200,
    })
  })

  it('falls back for unsupported provider, role, empty scopes, and zero ttl', () => {
    expect(
      ssoConfigToForm({
        ...baseSsoConfig,
        provider: 'saml',
        allowed_domains: [],
        scopes: [],
        default_role: 'owner',
        session_ttl_seconds: 0,
      }),
    ).toMatchObject({
      provider: 'none',
      allowed_domains: '',
      scopes: DEFAULT_SSO_FORM.scopes,
      default_role: 'viewer',
      session_ttl_seconds: DEFAULT_SSO_FORM.session_ttl_seconds,
    })
  })
})
