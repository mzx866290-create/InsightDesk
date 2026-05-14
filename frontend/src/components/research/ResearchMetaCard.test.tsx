import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ResearchTaskMeta } from '../../utils/researchTask'
import { ResearchMetaCard } from './ResearchMetaCard'

const meta: ResearchTaskMeta = {
  query: '今天广东哪里有雇员招聘？',
  rewrittenQuery: '广东 雇员 招聘 公告',
  mode: 'quick',
  requestedMode: 'quick',
  effectiveMode: 'quick',
  didFallback: false,
  fallbackNote: '',
  provider: 'searxng',
  providerSummary: 'searxng',
  summary: '',
  sourceCount: 2,
  sourceStrategy: 'community_first',
  facets: [],
  caveats: [],
  strategyIntent: 'job_search',
  strategyRegion: '广东',
  strategyFreshness: 'recent',
  strategySourceTypes: ['official', 'recruitment_platform'],
  strategyQueryVariants: ['广东 雇员 招聘 公告', '广东 事业单位 雇员 招聘'],
  strategyRankingPolicy: 'prefer recent official sources',
  relatedQuestions: ['报名条件和截止时间是什么？', '还有哪些官方来源可核验？'],
  findingCount: 0,
  contradictionCount: 0,
  roundCount: 0,
}

describe('ResearchMetaCard', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders planned search strategy metadata', () => {
    render(<ResearchMetaCard meta={meta} />)

    const strategy = screen.getByTestId('research-search-strategy')
    expect(strategy).toBeInTheDocument()
    expect(screen.getByText('Intent: job search')).toBeInTheDocument()
    expect(screen.getByText('Source: community first')).toBeInTheDocument()
    expect(screen.getByText('Region: 广东')).toBeInTheDocument()
    expect(screen.getByText('Freshness: recent')).toBeInTheDocument()
    expect(screen.getByText('official')).toBeInTheDocument()
    expect(screen.getByText('recruitment platform')).toBeInTheDocument()
    expect(within(strategy).getByText('广东 雇员 招聘 公告')).toBeInTheDocument()
    expect(screen.getByText('Ranking: prefer recent official sources')).toBeInTheDocument()
  })

  it('renders related follow-up questions', () => {
    render(<ResearchMetaCard meta={meta} />)

    const relatedQuestions = screen.getByTestId('research-related-questions')
    expect(relatedQuestions).toBeInTheDocument()
    expect(within(relatedQuestions).getByText('报名条件和截止时间是什么？')).toBeInTheDocument()
    expect(within(relatedQuestions).getByText('还有哪些官方来源可核验？')).toBeInTheDocument()
  })
})
