import { describe, expect, it } from 'vitest'

import { translations } from './index'

describe('i18n translations', () => {
  it('keeps Chinese and English translation keys aligned', () => {
    const zhKeys = Object.keys(translations['zh-CN']).sort()
    const enKeys = Object.keys(translations['en-US']).sort()

    expect(enKeys).toEqual(zhKeys)
  })

  it('does not contain common mojibake markers in visible copy', () => {
    const mojibakePattern = /[�]|褰|鍓|宸|娓|缂|鍒|杩|涔|閰|瘑|绠|瀵/

    for (const [language, entries] of Object.entries(translations)) {
      for (const [key, value] of Object.entries(entries)) {
        expect(value, `${language}.${key}`).not.toMatch(mojibakePattern)
      }
    }
  })
})
