/**
 * 对话导出工具函数
 * 支持将对话消息导出为 Markdown 格式文件
 * 根据 20260413plan.md P2 改进项实施
 */

import type { PanelMessage } from '../stores/chatStore'
import type { Session } from '../api/client'

/**
 * 格式化时间戳
 */
function formatTimestamp(ts?: number): string {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * 将 PanelMessage 列表转换为 Markdown 文本
 */
function messagesToMarkdown(
  session: Session | null,
  messages: PanelMessage[],
  modelLabel?: string,
): string {
  const lines: string[] = []

  // 标题
  const title = session?.title || '对话记录'
  lines.push(`# ${title}`)
  lines.push('')

  // 元信息
  const meta: string[] = []
  meta.push(`- **导出时间**：${formatTimestamp(Date.now())}`)
  if (session?.created_at) {
    meta.push(`- **创建时间**：${formatTimestamp(session.created_at * 1000)}`)
  }
  if (modelLabel) {
    meta.push(`- **模型**：${modelLabel}`)
  }
  meta.push(`- **消息数**：${messages.filter(m => m.role !== 'error').length}`)
  lines.push(...meta)
  lines.push('')
  lines.push('---')
  lines.push('')

  // 消息内容
  for (const msg of messages) {
    if (msg.role === 'error') continue

    if (msg.role === 'user') {
      lines.push('**🧑 用户**')
      lines.push('')
      // 附件信息
      if (msg.files && msg.files.length > 0) {
        const fileNames = msg.files.map(f => f.name || '附件').join('、')
        lines.push(`> 📎 附件：${fileNames}`)
        lines.push('')
      }
      lines.push(msg.content || '')
      if (msg.timestamp) {
        lines.push('')
        lines.push(`<sub>${formatTimestamp(msg.timestamp)}</sub>`)
      }
    } else if (msg.role === 'assistant') {
      const modelName = msg.modelId || modelLabel || '助手'
      lines.push(`**🤖 ${modelName}**`)
      lines.push('')
      lines.push(msg.content || '')

      // 引用来源
      if (msg.sources && msg.sources.length > 0) {
        lines.push('')
        lines.push('**参考来源：**')
        msg.sources.forEach((src, i) => {
          const srcName = src.title || `来源${i + 1}`
          lines.push(`[^${i + 1}]: ${srcName}${src.snippet ? ` — ${src.snippet.slice(0, 80)}...` : ''}`)
        })
      }

      if (msg.timestamp) {
        lines.push('')
        lines.push(`<sub>${formatTimestamp(msg.timestamp)}</sub>`)
      }
    }

    lines.push('')
    lines.push('---')
    lines.push('')
  }

  return lines.join('\n')
}

/**
 * 触发浏览器下载文件
 */
function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 生成安全的文件名（去除非法字符）
 */
function safeFilename(title: string): string {
  return title
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, '_')
    .slice(0, 60)
}

/**
 * 导出对话为 Markdown 文件
 * @param session 当前会话信息
 * @param messages 要导出的消息列表（来自某个 panel）
 * @param modelLabel 模型名称标签（可选）
 */
export function exportConversationAsMarkdown(
  session: Session | null,
  messages: PanelMessage[],
  modelLabel?: string,
): void {
  const content = messagesToMarkdown(session, messages, modelLabel)
  const title = session?.title || '对话记录'
  const dateStr = new Date().toISOString().slice(0, 10)
  const filename = `${safeFilename(title)}_${dateStr}.md`
  downloadFile(content, filename, 'text/markdown;charset=utf-8')
}
