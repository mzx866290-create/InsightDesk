import React, { useEffect } from 'react'
import { AlertCircle, CheckCircle2, ChevronUp, Circle, Zap } from 'lucide-react'

import { useWorkflowStore } from '../../stores/workflowStore'

interface WorkflowVisualizerProps {
  panelId: string
  onCollapse?: () => void
}

export const WorkflowVisualizer: React.FC<WorkflowVisualizerProps> = ({ panelId, onCollapse }) => {
  const workflow = useWorkflowStore((s) => s.getWorkflow(panelId))
  const initWorkflow = useWorkflowStore((s) => s.initWorkflow)

  useEffect(() => {
    if (!workflow) {
      initWorkflow(panelId)
    }
  }, [panelId, workflow, initWorkflow])

  if (!workflow || !workflow.isVisible) {
    return null
  }

  const getNodeIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={16} className="text-accent-green" />
      case 'running':
        return <Zap size={16} className="animate-pulse text-accent-blue" />
      case 'failed':
        return <AlertCircle size={16} className="text-accent-red" />
      default:
        return <Circle size={16} className="text-text-secondary/40" />
    }
  }

  const getNodeBgColor = (status: string, isActive: boolean) => {
    if (isActive) return 'bg-accent-blue/10 border-accent-blue/30'
    switch (status) {
      case 'completed':
        return 'bg-accent-green/5 border-accent-green/20'
      case 'running':
        return 'bg-accent-blue/10 border-accent-blue/30'
      case 'failed':
        return 'bg-accent-red/10 border-accent-red/30'
      default:
        return 'bg-bg-secondary border-bg-border'
    }
  }

  const formatDuration = (ms?: number) => {
    if (!ms) return ''
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  return (
    <div className="flex max-h-[min(42vh,32rem)] min-h-0 flex-col gap-3 overflow-hidden rounded-lg border border-bg-border bg-bg-secondary/50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold text-text-secondary">LangGraph 执行流程</div>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            title="收起执行流程"
          >
            <ChevronUp size={11} />
            <span>收起</span>
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {workflow.nodes.map((node, index) => {
          const isActive = workflow.currentNodeId === node.id

          return (
            <div key={node.id} className="flex items-start gap-2">
              <div className="mt-0.5 shrink-0">{getNodeIcon(node.status)}</div>

              <div
                className={`flex-1 min-w-0 rounded border px-2.5 py-1.5 transition-all ${getNodeBgColor(
                  node.status,
                  isActive,
                )}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium text-text-primary">{node.displayName}</div>

                    {node.toolName && (
                      <div className="mt-0.5 truncate text-[10px] text-text-secondary/70">
                        工具: {node.toolName}
                      </div>
                    )}

                    {node.toolParams && Object.keys(node.toolParams).length > 0 && (
                      <div className="mt-1 space-y-0.5 text-[10px] text-text-secondary/60">
                        {Object.entries(node.toolParams)
                          .slice(0, 2)
                          .map(([key, value]) => {
                            const text = String(value)
                            return (
                              <div key={key} className="truncate">
                                {key}: {text.slice(0, 30)}
                                {text.length > 30 ? '...' : ''}
                              </div>
                            )
                          })}
                      </div>
                    )}

                    {node.toolResult && (
                      <div className="mt-1 line-clamp-2 text-[10px] text-text-secondary/60">
                        结果: {node.toolResult}
                      </div>
                    )}

                    {node.retrievalMeta && (
                      <div className="mt-1 space-y-0.5 text-[10px] text-text-secondary/65">
                        {node.retrievalMeta.primary_mode && (
                          <div className="truncate">检索模式: {node.retrievalMeta.primary_mode}</div>
                        )}
                        {typeof node.retrievalMeta.source_count === 'number' && (
                          <div className="truncate">
                            来源数: {node.retrievalMeta.source_count}
                            {node.retrievalMeta.top_score !== null &&
                            node.retrievalMeta.top_score !== undefined
                              ? ` | top score ${Number(node.retrievalMeta.top_score).toFixed(3)}`
                              : ''}
                          </div>
                        )}
                        {node.retrievalMeta.matched_terms &&
                          node.retrievalMeta.matched_terms.length > 0 && (
                            <div className="truncate">
                              命中词: {node.retrievalMeta.matched_terms.join(' / ')}
                            </div>
                          )}
                      </div>
                    )}

                    {node.error && (
                      <div className="mt-1 truncate text-[10px] text-accent-red/80">
                        错误: {node.error}
                      </div>
                    )}
                  </div>

                  {node.duration && (
                    <div className="shrink-0 text-[10px] text-text-secondary/60">
                      {formatDuration(node.duration)}
                    </div>
                  )}
                </div>
              </div>

              {index < workflow.nodes.length - 1 && (
                <div className="absolute left-[calc(1.5rem+8px)] -ml-4 mt-6 h-4 w-0.5 bg-bg-border/50" />
              )}
            </div>
          )
        })}
      </div>

      <div className="border-t border-bg-border/50 pt-2 text-[10px] text-text-secondary/60">
        {workflow.nodes.filter((node) => node.status === 'completed').length}/{workflow.nodes.length} 完成
      </div>
    </div>
  )
}
