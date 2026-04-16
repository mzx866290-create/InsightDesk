import type { SSEChunk } from './client'

export interface WorkflowStateEvent {
  type: 'node_state'
  node_name: string
  status: 'running' | 'completed' | 'failed'
  duration_ms?: number
  tool_name?: string
  tool_params?: Record<string, unknown>
  tool_result_summary?: string
  retrieval_meta?: {
    primary_mode?: string
    modes?: string[]
    channels?: string[]
    source_count?: number
    source_titles?: string[]
    matched_terms?: string[]
    top_score?: number | null
  }
  error?: string
  timestamp: number
}

export function parseWorkflowEvent(chunk: SSEChunk): WorkflowStateEvent | null {
  if (chunk.type !== 'workflow_state') {
    return null
  }

  return {
    type: 'node_state',
    node_name: chunk.node_name || '',
    status: chunk.status || 'running',
    duration_ms: chunk.duration_ms,
    tool_name: chunk.tool_name,
    tool_params: chunk.tool_params,
    tool_result_summary: chunk.tool_result_summary,
    retrieval_meta: chunk.retrieval_meta,
    error: chunk.error,
    timestamp: chunk.timestamp || Date.now(),
  }
}
