import React, { useEffect } from 'react'
import { useWorkflowStore } from '../../stores/workflowStore'
import { CheckCircle2, Circle, AlertCircle, Zap } from 'lucide-react'

interface WorkflowVisualizerProps {
  panelId: string
}

export const WorkflowVisualizer: React.FC<WorkflowVisualizerProps> = ({ panelId }) => {
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
        return <Zap size={16} className="text-accent-blue animate-pulse" />
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
    <div className="flex flex-col gap-3 p-3 bg-bg-secondary/50 rounded-lg border border-bg-border">
      <div className="text-xs font-semibold text-text-secondary">LangGraph 执行流程</div>
      
      <div className="flex flex-col gap-2">
        {workflow.nodes.map((node, index) => {
          const isActive = workflow.currentNodeId === node.id
          const isCompleted = node.status === 'completed'
          const isFailed = node.status === 'failed'
          
          return (
            <div key={node.id} className="flex items-start gap-2">
              {/* Node icon */}
              <div className="flex-shrink-0 mt-0.5">
                {getNodeIcon(node.status)}
              </div>

              {/* Node content */}
              <div className={`flex-1 min-w-0 px-2.5 py-1.5 rounded border transition-all ${getNodeBgColor(node.status, isActive)}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-text-primary">
                      {node.displayName}
                    </div>
                    
                    {/* Tool info */}
                    {node.toolName && (
                      <div className="text-[10px] text-text-secondary/70 mt-0.5 truncate">
                        工具: {node.toolName}
                      </div>
                    )}
                    
                    {/* Tool params */}
                    {node.toolParams && Object.keys(node.toolParams).length > 0 && (
                      <div className="text-[10px] text-text-secondary/60 mt-1 space-y-0.5">
                        {Object.entries(node.toolParams).slice(0, 2).map(([key, value]) => (
                          <div key={key} className="truncate">
                            {key}: {String(value).slice(0, 30)}
                            {String(value).length > 30 ? '...' : ''}
                          </div>
                        ))}
                      </div>
                    )}

                    {node.toolResult && (
                      <div className="text-[10px] text-text-secondary/60 mt-1 line-clamp-2">
                        结果: {node.toolResult}
                      </div>
                    )}

                    {node.retrievalMeta && (
                      <div className="mt-1 space-y-0.5 text-[10px] text-text-secondary/65">
                        {node.retrievalMeta.primary_mode && (
                          <div className="truncate">
                            检索模式: {node.retrievalMeta.primary_mode}
                          </div>
                        )}
                        {typeof node.retrievalMeta.source_count === 'number' && (
                          <div className="truncate">
                            来源数: {node.retrievalMeta.source_count}
                            {node.retrievalMeta.top_score !== null && node.retrievalMeta.top_score !== undefined
                              ? ` · top score ${Number(node.retrievalMeta.top_score).toFixed(3)}`
                              : ''}
                          </div>
                        )}
                        {node.retrievalMeta.matched_terms && node.retrievalMeta.matched_terms.length > 0 && (
                          <div className="truncate">
                            命中词: {node.retrievalMeta.matched_terms.join(' / ')}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* Error message */}
                    {node.error && (
                      <div className="text-[10px] text-accent-red/80 mt-1 truncate">
                        错误: {node.error}
                      </div>
                    )}
                  </div>

                  {/* Duration */}
                  {node.duration && (
                    <div className="text-[10px] text-text-secondary/60 flex-shrink-0">
                      {formatDuration(node.duration)}
                    </div>
                  )}
                </div>
              </div>

              {/* Connector line */}
              {index < workflow.nodes.length - 1 && (
                <div className="absolute left-[calc(1.5rem+8px)] w-0.5 h-4 bg-bg-border/50 -ml-4 mt-6" />
              )}
            </div>
          )
        })}
      </div>

      {/* Status summary */}
      <div className="text-[10px] text-text-secondary/60 pt-2 border-t border-bg-border/50">
        {workflow.nodes.filter((n) => n.status === 'completed').length}/{workflow.nodes.length} 完成
      </div>
    </div>
  )
}
