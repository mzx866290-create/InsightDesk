import type { ResearchMode, ResearchSourceStrategy } from '../../stores/chatStore'
import type { ResearchRequestConfig } from './messageInputUtils'

export interface ResearchSourceStrategyOption {
  value: ResearchSourceStrategy
  label: string
  title: string
}

export const RESEARCH_SOURCE_STRATEGY_OPTIONS: ResearchSourceStrategyOption[] = [
  {
    value: 'web_only',
    label: '网页',
    title: '优先使用网页来源进行标准研究',
  },
  {
    value: 'community_first',
    label: '社区',
    title: '优先使用可检索的社区和论坛线索，并进行独立验证',
  },
  {
    value: 'evidence_strict',
    label: '严谨',
    title: '严格证据模式；社区内容仅作为背景线索，除非能被独立验证',
  },
]

export const RESEARCH_REQUEST_CONFIG: Record<ResearchMode, ResearchRequestConfig> = {
  quick: {
    searchDepth: 'basic',
    maxResults: 5,
    maxRounds: 1,
    maxResultsPerQuery: 2,
  },
  deep: {
    searchDepth: 'advanced',
    maxResults: 8,
    maxRounds: 2,
    maxResultsPerQuery: 4,
  },
}

export function getEffectiveComposerResearchMode(
  researchMode: ResearchMode,
  researchSourceStrategy: ResearchSourceStrategy,
): ResearchMode {
  return researchSourceStrategy === 'web_only' ? researchMode : 'deep'
}

export function getResearchModeLabel(researchMode: ResearchMode): string {
  return researchMode === 'quick' ? '快研' : '深研'
}

export function getResearchSourceStrategyLabel(
  researchSourceStrategy: ResearchSourceStrategy,
): string {
  if (researchSourceStrategy === 'community_first') return '社区'
  if (researchSourceStrategy === 'evidence_strict') return '严谨'
  if (researchSourceStrategy === 'web_and_community') return '网页+社区'
  return '网页'
}
