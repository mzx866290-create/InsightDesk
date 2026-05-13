import { describe, expect, it } from 'vitest'

import { formatAuditTime, safeAuditDetails } from './integratorAuditModel'

describe('integratorAuditModel', () => {
  it('formats audit time and filters sensitive audit details', () => {
    expect(formatAuditTime(0)).toBe('-')
    expect(safeAuditDetails({
      token: 'raw-token',
      url: 'https://example.invalid',
      action: 'ok',
      nested: { value: 1 },
      safe: 'value',
    })).toEqual([
      ['action', 'ok'],
      ['nested', '{"value":1}'],
      ['safe', 'value'],
    ])
  })
})
