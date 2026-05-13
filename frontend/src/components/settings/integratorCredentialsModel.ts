export type CredentialMode = 'fields' | 'json'

export type CredentialInputKey =
  | 'token'
  | 'api_key'
  | 'client_id'
  | 'client_secret'
  | 'username'
  | 'password'
  | 'authorization'

export type CredentialFormValues = Record<CredentialInputKey, string>

export interface CredentialFieldDefinition {
  key: CredentialInputKey
  label: string
  placeholder: string
  sensitive: boolean
}

export interface CredentialTemplate {
  id: string
  label: string
  description: string
  fields: CredentialInputKey[]
}

export const DEFAULT_CREDENTIAL_PATCH_JSON = '{\n  "token": ""\n}'
export const DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS = 3
export const MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS = 0.1
export const MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS = 10

const SENSITIVE_PROBE_DISPLAY_KEY_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|api_key|key)/i
const URL_LIKE_VALUE_PATTERN = /^https?:\/\//i

export const EMPTY_CREDENTIAL_FORM: CredentialFormValues = {
  token: '',
  api_key: '',
  client_id: '',
  client_secret: '',
  username: '',
  password: '',
  authorization: '',
}

const CREDENTIAL_FIELD_DEFINITIONS: CredentialFieldDefinition[] = [
  { key: 'token', label: 'Token', placeholder: 'Paste a bearer or webhook token', sensitive: true },
  { key: 'api_key', label: 'API key', placeholder: 'Paste an API key', sensitive: true },
  { key: 'client_id', label: 'Client ID', placeholder: 'OAuth client identifier', sensitive: false },
  { key: 'client_secret', label: 'Client secret', placeholder: 'Paste the OAuth client secret', sensitive: true },
  { key: 'username', label: 'Username', placeholder: 'Basic auth username', sensitive: false },
  { key: 'password', label: 'Password', placeholder: 'Basic auth password', sensitive: true },
  { key: 'authorization', label: 'Authorization header', placeholder: 'Bearer, Basic, or custom header value', sensitive: true },
]

export const CREDENTIAL_TEMPLATES: CredentialTemplate[] = [
  {
    id: 'token',
    label: 'Token',
    description: 'Rotate a single token field.',
    fields: ['token'],
  },
  {
    id: 'api_key',
    label: 'API key',
    description: 'Rotate API key based integrations.',
    fields: ['api_key'],
  },
  {
    id: 'oauth_client',
    label: 'OAuth client',
    description: 'Rotate client_id and client_secret together.',
    fields: ['client_id', 'client_secret'],
  },
  {
    id: 'basic_auth',
    label: 'Basic auth',
    description: 'Rotate username and password fields.',
    fields: ['username', 'password'],
  },
  {
    id: 'authorization',
    label: 'Auth header',
    description: 'Rotate a full authorization header value.',
    fields: ['authorization'],
  },
]

export function parseCredentialsPatchJson(value: string): Record<string, unknown> {
  const parsed = JSON.parse(value.trim() || '{}') as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Credential patch must be a JSON object.')
  }
  return parsed as Record<string, unknown>
}

export function credentialTemplateById(templateId: string): CredentialTemplate {
  return CREDENTIAL_TEMPLATES.find((template) => template.id === templateId) ?? CREDENTIAL_TEMPLATES[0]
}

export function credentialFieldDefinition(field: CredentialInputKey): CredentialFieldDefinition {
  return CREDENTIAL_FIELD_DEFINITIONS.find((definition) => definition.key === field) ?? CREDENTIAL_FIELD_DEFINITIONS[0]
}

export function buildCredentialPatchFromFields(
  values: CredentialFormValues,
  fields: CredentialInputKey[],
): Record<string, unknown> {
  const patch = Object.fromEntries(
    fields
      .map((field) => [field, values[field].trim()] as const)
      .filter(([, value]) => value.length > 0),
  )
  if (Object.keys(patch).length === 0) {
    throw new Error('Enter at least one credential field or switch to JSON patch.')
  }
  return patch
}

export function formatFieldList(fields: string[]): string {
  return fields.length > 0 ? fields.join(', ') : '-'
}

export function clampExternalProbeTimeout(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS
  return Math.max(
    MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS,
    Math.min(MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS, value),
  )
}

export function safeProbeEntries(record: Record<string, unknown> | undefined): Array<[string, string]> {
  if (!record) return []
  return Object.entries(record)
    .filter(([key]) => !SENSITIVE_PROBE_DISPLAY_KEY_PATTERN.test(key))
    .map(([key, value]) => {
      const rendered = typeof value === 'string' ? value : JSON.stringify(value)
      return [key, rendered ?? ''] as [string, string]
    })
    .filter(([, value]) => value && !URL_LIKE_VALUE_PATTERN.test(value) && !SENSITIVE_PROBE_DISPLAY_KEY_PATTERN.test(value))
    .slice(0, 4)
}
