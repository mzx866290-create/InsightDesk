import React, { useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { getKBHealth, type KBHealthData } from '../../api/client'
import { isAdminAccessError } from '../admin/adminAccess'
import { KbHealthSummaryPanel } from './KbHealthSummaryPanel'

interface KnowledgeBaseHealthTabProps {
  onAdminAccessError?: (message: string | null) => void
}

export const KnowledgeBaseHealthTab: React.FC<KnowledgeBaseHealthTabProps> = ({
  onAdminAccessError,
}) => {
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState<KBHealthData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [documentsVisible, setDocumentsVisible] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getKBHealth()
      setHealth(data)
      onAdminAccessError?.(null)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '获取状态失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    } finally {
      setLoading(false)
    }
  }, [onAdminAccessError])

  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={20} className="animate-spin text-accent-blue mr-2" />
        <span className="text-sm text-text-secondary">加载中...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8 space-y-3">
        <AlertCircle size={32} className="mx-auto text-accent-red" />
        <p className="text-sm text-accent-red">{error}</p>
        <button onClick={load} className="px-3 py-1.5 text-xs rounded-lg border border-bg-border text-text-secondary hover:bg-bg-hover transition-colors">
          重试
        </button>
      </div>
    )
  }

  if (!health) return null

  return (
    <div className="space-y-4">
      <KbHealthSummaryPanel
        health={health}
        documentsVisible={documentsVisible}
        onToggleDocuments={() => setDocumentsVisible((value) => !value)}
      />

      <button
        onClick={load}
        className="w-full py-2 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover border border-bg-border transition-colors flex items-center justify-center gap-1.5"
      >
        <RefreshCw size={11} />
        刷新状态
      </button>
    </div>
  )
}
