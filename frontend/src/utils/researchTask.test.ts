import { describe, expect, it } from 'vitest'

import type { TaskRecord } from '../api/client'
import { getResearchTaskMeta } from './researchTask'

function task(params: Record<string, unknown>): TaskRecord {
  return {
    task_id: 'task-1',
    task_type: 'web_research',
    status: 'completed',
    progress: 100,
    params,
    created_at: 1,
    updated_at: 2,
  }
}

describe('getResearchTaskMeta', () => {
  it('extracts model-planned search strategy metadata', () => {
    const meta = getResearchTaskMeta(
      task({
        query: '今天广东哪里有雇员招聘？',
        research_mode: 'quick',
        research_source_strategy: 'community_first',
        research_provider: 'searxng',
        search_strategy_plan: {
          intent: 'job_search',
          region: '广东',
          freshness: 'recent',
          source_types: ['official', 'recruitment_platform', 'local_government'],
          primary_query: '广东 雇员 招聘 公告',
          query_variants: ['广东 雇员 招聘 公告', '广东 事业单位 雇员 招聘'],
          ranking_policy: 'prefer recent official sources',
        },
        research_related_questions: ['报名条件和截止时间是什么？', '还有哪些官方来源可核验？'],
      }),
    )

    expect(meta?.sourceStrategy).toBe('community_first')
    expect(meta?.strategyIntent).toBe('job_search')
    expect(meta?.strategyRegion).toBe('广东')
    expect(meta?.strategyFreshness).toBe('recent')
    expect(meta?.strategySourceTypes).toEqual([
      'official',
      'recruitment_platform',
      'local_government',
    ])
    expect(meta?.strategyQueryVariants).toEqual([
      '广东 雇员 招聘 公告',
      '广东 事业单位 雇员 招聘',
    ])
    expect(meta?.strategyRankingPolicy).toBe('prefer recent official sources')
    expect(meta?.relatedQuestions).toEqual([
      '报名条件和截止时间是什么？',
      '还有哪些官方来源可核验？',
    ])
  })
})
