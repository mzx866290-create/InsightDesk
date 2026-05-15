import type { Session } from '../api/client'

export const DEMO_SESSION_PREFIX = 'demo-'

export const DEMO_BACKEND_NOTICE =
  '演示模式：当前未连接后端，新建对话和输入仅在本页临时展示。'

export const DEMO_ASSISTANT_MESSAGE =
  '这是前端演示模式：当前页面没有连接 FastAPI 后端，所以不会真正调用模型、知识库或联网研究。完整体验需要本地运行 start.bat，或在 Vercel 配置 VITE_API_BASE_URL 指向已部署的后端服务。'

export function isDemoSessionId(sessionId: string | null | undefined): boolean {
  return Boolean(sessionId?.startsWith(DEMO_SESSION_PREFIX))
}

export function createLocalDemoSession(
  titleSeed: string,
  workspaceId: string,
): Session {
  const now = Date.now() / 1000
  const safeTitle = titleSeed.trim().slice(0, 40) || '新建对话'
  const suffix = Math.random().toString(36).slice(2, 8)

  return {
    session_id: `${DEMO_SESSION_PREFIX}${Math.round(now * 1000)}-${suffix}`,
    title: safeTitle,
    created_at: now,
    updated_at: now,
    message_count: 0,
    is_archived: false,
    is_favorite: false,
    is_pinned: false,
    session_order: 0,
    tags: [],
    workspace_id: workspaceId,
  }
}
