/**
 * 错误码映射表：将技术错误码转换为用户友好的提示文案
 * 根据 20260413plan.md P1 改进项实施
 */

export interface ErrorMessage {
  title: string
  suggestion: string
  /** 建议显示的操作按钮 */
  action?: 'settings' | 'clear' | 'retry' | 'none'
}

export const ERROR_MESSAGES: Record<string, ErrorMessage> = {
  // 认证与授权
  AUTH_FAILED: {
    title: '认证失败，无法连接到模型服务',
    suggestion: '请检查 API Key 是否正确，可在右上角设置中更新',
    action: 'settings',
  },
  INVALID_API_KEY: {
    title: 'API Key 无效',
    suggestion: '请前往设置更新有效的 API Key',
    action: 'settings',
  },

  // 模型相关
  MODEL_NOT_FOUND: {
    title: '找不到指定的模型',
    suggestion: '请确认模型名称拼写正确，或在面板中切换其他可用模型',
    action: 'settings',
  },
  MODEL_OVERLOADED: {
    title: '模型服务繁忙',
    suggestion: '当前模型负载过高，请稍后重试或切换到其他模型',
    action: 'retry',
  },

  // 限流与配额
  RATE_LIMIT: {
    title: '请求过于频繁',
    suggestion: '已超出调用频率限制，请稍等片刻（约 30 秒）后再试',
    action: 'retry',
  },
  QUOTA_EXCEEDED: {
    title: 'API 配额已耗尽',
    suggestion: '本月 API 额度已用完，请前往服务商控制台充值或升级套餐',
    action: 'settings',
  },

  // 上下文与长度
  CONTEXT_LIMIT: {
    title: '对话上下文过长',
    suggestion: '消息历史已超出模型最大上下文长度，请清空对话历史后继续',
    action: 'clear',
  },
  CONTENT_TOO_LONG: {
    title: '输入内容过长',
    suggestion: '请缩短输入内容，单次输入建议不超过 4000 字',
    action: 'none',
  },

  // 网络与超时
  TIMEOUT: {
    title: '请求超时，未收到响应',
    suggestion: '网络可能不稳定，或模型响应时间过长，请稍后重试',
    action: 'retry',
  },
  NETWORK_ERROR: {
    title: '网络连接错误',
    suggestion: '请检查网络连接，或确认后端服务正在运行',
    action: 'retry',
  },
  CONNECTION_REFUSED: {
    title: '无法连接到后端服务',
    suggestion: '后端服务可能未启动，请运行"一键启动.bat"后刷新页面',
    action: 'none',
  },

  // 知识库
  KB_NOT_READY: {
    title: '知识库未就绪',
    suggestion: '请先上传文档并等待索引构建完成，再启用知识库功能',
    action: 'none',
  },
  KB_INDEX_FAILED: {
    title: '知识库索引失败',
    suggestion: '文档处理出现错误，请删除后重新上传，或检查文档格式是否受支持',
    action: 'none',
  },

  // 文件与附件
  FILE_TOO_LARGE: {
    title: '文件体积超限',
    suggestion: '单个文件不能超过 50MB，请压缩后重新上传',
    action: 'none',
  },
  UNSUPPORTED_FILE_TYPE: {
    title: '不支持的文件格式',
    suggestion: '目前支持 PDF、Word、Excel、CSV、TXT、图片等格式',
    action: 'none',
  },

  // 服务器错误
  INTERNAL_ERROR: {
    title: '服务器内部错误',
    suggestion: '服务端发生未预期的错误，请稍后重试。若持续发生请联系管理员',
    action: 'retry',
  },
  SERVICE_UNAVAILABLE: {
    title: '服务暂时不可用',
    suggestion: '服务正在维护中，请稍后再试',
    action: 'retry',
  },

  // 内容安全
  CONTENT_POLICY: {
    title: '内容不符合使用政策',
    suggestion: '请求内容触发了模型的安全策略，请修改提问后重试',
    action: 'clear',
  },
}

/**
 * 根据错误码获取用户友好的错误信息
 * @param errorCode 错误码（来自后端 SSE 事件或 HTTP 响应）
 * @param fallbackContent 当无法匹配错误码时显示的原始错误内容
 */
export function resolveErrorMessage(
  errorCode?: string,
  fallbackContent?: string,
): { title: string; suggestion?: string; action?: ErrorMessage['action'] } {
  if (!errorCode) {
    return {
      title: fallbackContent || '发生了未知错误',
      suggestion: '请稍后重试，如问题持续请刷新页面',
      action: 'retry',
    }
  }

  const mapped = ERROR_MESSAGES[errorCode]
  if (mapped) {
    return mapped
  }

  // 未知错误码：显示原始内容 + 通用建议
  return {
    title: fallbackContent || `发生错误（${errorCode}）`,
    suggestion: '请稍后重试，如问题持续请联系管理员',
    action: 'retry',
  }
}
