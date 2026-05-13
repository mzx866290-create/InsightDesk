import { describe, expect, it } from 'vitest'

import {
  buildCredentialPatchFromFields,
  clampExternalProbeTimeout,
  credentialFieldDefinition,
  credentialTemplateById,
  DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS,
  EMPTY_CREDENTIAL_FORM,
  formatFieldList,
  parseCredentialsPatchJson,
  safeProbeEntries,
} from './integratorCredentialsModel'

describe('integratorCredentialsModel', () => {
  it('builds credential patches and resolves template metadata', () => {
    expect(credentialTemplateById('oauth_client').fields).toEqual(['client_id', 'client_secret'])
    expect(credentialTemplateById('missing').id).toBe('token')
    expect(credentialFieldDefinition('password').sensitive).toBe(true)
    expect(credentialFieldDefinition('missing' as never).key).toBe('token')
    expect(
      buildCredentialPatchFromFields(
        {
          ...EMPTY_CREDENTIAL_FORM,
          token: '  rotated-token  ',
          client_id: ' client-1 ',
          client_secret: ' ',
        },
        ['token', 'client_id', 'client_secret'],
      ),
    ).toEqual({ token: 'rotated-token', client_id: 'client-1' })
    expect(() => buildCredentialPatchFromFields(EMPTY_CREDENTIAL_FORM, ['token'])).toThrow(
      'Enter at least one credential field or switch to JSON patch.',
    )
    expect(parseCredentialsPatchJson('{"token":"x"}')).toEqual({ token: 'x' })
    expect(parseCredentialsPatchJson('')).toEqual({})
    expect(() => parseCredentialsPatchJson('[]')).toThrow('Credential patch must be a JSON object.')
  })

  it('formats field lists and clamps external probe timeouts', () => {
    expect(formatFieldList(['a', 'b'])).toBe('a, b')
    expect(formatFieldList([])).toBe('-')
    expect(clampExternalProbeTimeout(Number.NaN)).toBe(DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS)
    expect(clampExternalProbeTimeout(0)).toBe(0.1)
    expect(clampExternalProbeTimeout(11)).toBe(10)
  })

  it('filters sensitive probe details', () => {
    expect(safeProbeEntries({
      token: 'raw-token',
      endpoint: 'https://example.invalid',
      status: 'ok',
      nested: { value: 1 },
      safe: 'value',
    })).toEqual([
      ['status', 'ok'],
      ['nested', '{"value":1}'],
      ['safe', 'value'],
    ])
  })
})
