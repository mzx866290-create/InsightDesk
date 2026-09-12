import { useState } from 'react'

import {
  getAnswerGroupReview,
  promotePanelAnswer,
  promoteRecommendedAnswerGroup,
  type AnswerGroupReviewResponse,
  type PromoteAnswerResponse,
} from '../../api/client'
import type { PanelMessage } from '../../stores/chatStore'

interface UseAnswerReviewOptions {
  currentSessionId: string | null
  applyPromotedAnswer: (payload: PromoteAnswerResponse) => void
}

export function useAnswerReview({
  currentSessionId,
  applyPromotedAnswer,
}: UseAnswerReviewOptions) {
  const [reviewAnswerGroupId, setReviewAnswerGroupId] = useState<string | null>(null)
  const [reviewData, setReviewData] = useState<AnswerGroupReviewResponse | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewPromotingPanelId, setReviewPromotingPanelId] = useState<string | null>(null)
  const [reviewPromotingRecommended, setReviewPromotingRecommended] = useState(false)

  const loadAnswerReview = async (answerGroupId: string) => {
    if (!currentSessionId) return
    setReviewLoading(true)
    setReviewError(null)
    try {
      const payload = await getAnswerGroupReview(currentSessionId, answerGroupId)
      setReviewData(payload)
    } catch (error) {
      setReviewError((error as Error).message || '加载答案评审失败')
      setReviewData(null)
    } finally {
      setReviewLoading(false)
    }
  }

  const handleOpenAnswerReview = async (message: PanelMessage) => {
    if (!currentSessionId || !message.answerGroupId) return
    setReviewAnswerGroupId(message.answerGroupId)
    setReviewData(null)
    setReviewError(null)
    await loadAnswerReview(message.answerGroupId)
  }

  const handleRefreshAnswerReview = async () => {
    if (!reviewAnswerGroupId) return
    await loadAnswerReview(reviewAnswerGroupId)
  }

  const handlePromoteReviewedPanel = async (sourcePanelId: string) => {
    if (!currentSessionId || !reviewAnswerGroupId) return
    setReviewPromotingPanelId(sourcePanelId)
    setReviewError(null)
    try {
      const payload = await promotePanelAnswer(currentSessionId, reviewAnswerGroupId, sourcePanelId)
      applyPromotedAnswer(payload)
      setReviewAnswerGroupId(null)
    } catch (error) {
      setReviewError((error as Error).message || '设置主答案失败')
    } finally {
      setReviewPromotingPanelId(null)
    }
  }

  const handlePromoteRecommendedAnswer = async () => {
    if (!currentSessionId || !reviewAnswerGroupId) return
    setReviewPromotingRecommended(true)
    setReviewError(null)
    try {
      const payload = await promoteRecommendedAnswerGroup(currentSessionId, reviewAnswerGroupId)
      applyPromotedAnswer(payload)
      setReviewAnswerGroupId(null)
    } catch (error) {
      setReviewError((error as Error).message || '采用推荐答案失败')
    } finally {
      setReviewPromotingRecommended(false)
    }
  }

  const closeReview = () => {
    setReviewAnswerGroupId(null)
    setReviewData(null)
    setReviewError(null)
    setReviewPromotingPanelId(null)
    setReviewPromotingRecommended(false)
  }

  return {
    reviewAnswerGroupId,
    reviewData,
    reviewLoading,
    reviewError,
    reviewPromotingPanelId,
    reviewPromotingRecommended,
    closeReview,
    handleOpenAnswerReview,
    handleRefreshAnswerReview,
    handlePromoteReviewedPanel,
    handlePromoteRecommendedAnswer,
  }
}
