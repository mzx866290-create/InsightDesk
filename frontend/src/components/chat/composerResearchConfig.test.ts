import { describe, expect, it } from 'vitest'

import {
  RESEARCH_REQUEST_CONFIG,
  RESEARCH_SOURCE_STRATEGY_OPTIONS,
  getEffectiveComposerResearchMode,
  getResearchModeLabel,
  getResearchSourceStrategyLabel,
} from './composerResearchConfig'

describe('composerResearchConfig', () => {
  it('forces deep research for non-web-only source strategies', () => {
    expect(getEffectiveComposerResearchMode('quick', 'web_only')).toBe('quick')
    expect(getEffectiveComposerResearchMode('quick', 'community_first')).toBe('deep')
    expect(getEffectiveComposerResearchMode('deep', 'evidence_strict')).toBe('deep')
  })

  it('keeps user-facing research labels centralized', () => {
    expect(getResearchModeLabel('quick')).toBe('快研')
    expect(getResearchModeLabel('deep')).toBe('深研')
    expect(getResearchSourceStrategyLabel('web_only')).toBe('网页')
    expect(getResearchSourceStrategyLabel('community_first')).toBe('社区')
    expect(getResearchSourceStrategyLabel('evidence_strict')).toBe('严谨')
    expect(getResearchSourceStrategyLabel('web_and_community')).toBe('网页+社区')
  })

  it('exports the available toolbar source strategies and request presets', () => {
    expect(RESEARCH_SOURCE_STRATEGY_OPTIONS.map((option) => option.value)).toEqual([
      'web_only',
      'community_first',
      'evidence_strict',
    ])
    expect(RESEARCH_REQUEST_CONFIG.quick.maxRounds).toBe(1)
    expect(RESEARCH_REQUEST_CONFIG.deep.maxRounds).toBe(2)
  })
})
