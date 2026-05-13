import React from 'react'
import type { RetrievalTestResult } from '../../api/client'
import { KbRetrievalDebugList } from './KbRetrievalDebugList'
import {
  hasKbRetrievalTopResults,
  KB_RETRIEVAL_CANDIDATE_LISTS,
  type KbRetrievalResultVariant,
} from './KbRetrievalResultModel'

interface KbRetrievalCandidateListsProps {
  result: RetrievalTestResult
  variant: KbRetrievalResultVariant
}

export function KbRetrievalCandidateLists({ result, variant }: KbRetrievalCandidateListsProps) {
  if (!hasKbRetrievalTopResults(result)) return null

  const lists = KB_RETRIEVAL_CANDIDATE_LISTS.map((list) => (
    <KbRetrievalDebugList
      key={list.key}
      title={list.titles[variant]}
      items={result[list.key]}
      tone={list.tone}
    />
  ))

  if (variant === 'diagnostic') return <>{lists}</>

  return <div className="space-y-3">{lists}</div>
}
