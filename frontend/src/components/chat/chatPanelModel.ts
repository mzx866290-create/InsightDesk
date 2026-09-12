import type { Message, SystemPrompt } from '../../api/client'
import type { PanelMessage } from '../../stores/chatStore'

export const DEFAULT_STARTERS = [
  '帮我总结知识库里的核心内容',
  '查询最新行业动态',
  '帮我分析上传的文档',
  '生成一份数据可视化仪表盘',
]

// 根据角色名称推断快捷提问
export function getStartersForPrompt(prompt: SystemPrompt | null): string[] {
  if (!prompt) return DEFAULT_STARTERS
  const name = prompt.name.toLowerCase()
  if (name.includes('代码') || name.includes('code')) {
    return ['帮我审查这段代码', '解释这个函数的作用', '找出潜在的安全漏洞', '优化代码性能']
  }
  if (name.includes('文档') || name.includes('写作')) {
    return ['帮我撰写技术文档', '优化这段文字的表达', '生成 API 说明文档', '写一份项目 README']
  }
  if (name.includes('简历') || name.includes('hr') || name.includes('招聘')) {
    return ['分析候选人简历', '生成岗位职责描述', '提取简历关键信息', '对比多份简历']
  }
  return DEFAULT_STARTERS
}

export function mapMessages(messages: Message[]): PanelMessage[] {
  return messages.map((message, index) => ({
    id: typeof message.id === 'number' ? `db-${message.id}` : `loaded-${index}`,
    serverMessageId: message.id,
    role: message.role,
    content: message.content,
    images: message.images,
    files: message.files,
    sources: message.sources,
    modelId: message.model_id,
    panelId: message.panel_id,
    answerGroupId: message.answer_group_id,
    taskId: message.task_id,
    taskType: message.task_type,
    workflowNodes: message.workflow_nodes,
    tokenUsage: message.token_usage,
    timestamp: message.timestamp,
    feedbackValue: message.feedback_value,
  }))
}

export function findLatestWorkflowNodes(messages: Message[]) {
  const latestAssistantMessage = [...messages]
    .reverse()
    .find(
      (message) =>
        message.role === 'assistant' && (message.workflow_nodes?.length ?? 0) > 0,
    )

  return latestAssistantMessage?.workflow_nodes ?? []
}
