import type { SsoConfig } from '../../api/client'

export type SsoConfigForm = {
  provider: 'none' | 'oidc'
  issuer_url: string
  authorization_endpoint: string
  token_endpoint: string
  jwks_url: string
  client_id: string
  client_secret: string
  clear_client_secret: boolean
  allowed_domains: string
  scopes: string
  default_role: 'viewer' | 'editor' | 'admin'
  session_ttl_seconds: number
}

export type SsoConfigFormChangeHandler = <Key extends keyof SsoConfigForm>(
  key: Key,
  value: SsoConfigForm[Key],
) => void

export const DEFAULT_SSO_FORM: SsoConfigForm = {
  provider: 'none',
  issuer_url: '',
  authorization_endpoint: '',
  token_endpoint: '',
  jwks_url: '',
  client_id: '',
  client_secret: '',
  clear_client_secret: false,
  allowed_domains: '',
  scopes: 'openid email profile',
  default_role: 'viewer',
  session_ttl_seconds: 28800,
}

export function ssoConfigToForm(config: SsoConfig | null): SsoConfigForm {
  if (!config) return DEFAULT_SSO_FORM
  return {
    provider: config.provider === 'oidc' ? 'oidc' : 'none',
    issuer_url: config.issuer_url ?? '',
    authorization_endpoint: config.authorization_endpoint ?? '',
    token_endpoint: config.token_endpoint ?? '',
    jwks_url: config.jwks_url ?? '',
    client_id: config.client_id ?? '',
    client_secret: '',
    clear_client_secret: false,
    allowed_domains: config.allowed_domains?.join(', ') ?? '',
    scopes: config.scopes?.join(' ') || DEFAULT_SSO_FORM.scopes,
    default_role: config.default_role === 'admin' || config.default_role === 'editor' ? config.default_role : 'viewer',
    session_ttl_seconds: config.session_ttl_seconds || DEFAULT_SSO_FORM.session_ttl_seconds,
  }
}
