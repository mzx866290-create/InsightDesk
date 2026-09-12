import type { ChatFile, ChatImage } from '../../api/client'
import type { ResearchSourceStrategy } from '../../stores/chatStore'

const readFileAsDataUrl = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error(`读取文件失败：${file.name}`))
    reader.readAsDataURL(file)
  })

const SUPPORTED_IMAGE_MEDIA_TYPES = new Set([
  'image/gif',
  'image/jpeg',
  'image/png',
  'image/webp',
])

const BASE64_PAYLOAD_PATTERN =
  /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/

export const MAX_IMAGE_COUNT = 4
export const MAX_IMAGE_FILE_SIZE_BYTES = 10 * 1024 * 1024
export const MAX_IMAGE_TOTAL_SIZE_BYTES = 20 * 1024 * 1024

export interface ImageAttachmentLimits {
  maxBytes: number
  maxCount: number
  maxTotalBytes: number
}

export interface ChatImageValidationResult {
  error: string | null
  sizeBytes: number
}

export interface ChatImageMergeResult {
  error: string | null
  images: ChatImage[]
}

export const DEFAULT_IMAGE_ATTACHMENT_LIMITS: Readonly<ImageAttachmentLimits> = {
  maxBytes: MAX_IMAGE_FILE_SIZE_BYTES,
  maxCount: MAX_IMAGE_COUNT,
  maxTotalBytes: MAX_IMAGE_TOTAL_SIZE_BYTES,
}

const formatImageLimit = (sizeBytes: number): string => {
  const sizeMb = sizeBytes / (1024 * 1024)
  return Number.isInteger(sizeMb) ? `${sizeMb} MB` : `${sizeMb.toFixed(1)} MB`
}

const normalizedMediaType = (mediaType: string): string =>
  mediaType.trim().toLowerCase().split(';', 1)[0]

const inspectImageDataUrl = (
  dataUrl: string,
): { mediaType: string; sizeBytes: number } | null => {
  if (!dataUrl.startsWith('data:')) return null

  const commaIndex = dataUrl.indexOf(',')
  if (commaIndex < 0) return null

  const metadata = dataUrl.slice(5, commaIndex).split(';')
  const mediaType = normalizedMediaType(metadata[0] ?? '')
  const isBase64 = metadata.slice(1).some((part) => part.trim().toLowerCase() === 'base64')
  const encoded = dataUrl.slice(commaIndex + 1)
  if (!isBase64 || !encoded || !BASE64_PAYLOAD_PATTERN.test(encoded)) return null

  const padding = encoded.endsWith('==') ? 2 : encoded.endsWith('=') ? 1 : 0
  return {
    mediaType,
    sizeBytes: (encoded.length / 4) * 3 - padding,
  }
}

export const validateImageFile = (
  file: File,
  limits: Readonly<ImageAttachmentLimits> = DEFAULT_IMAGE_ATTACHMENT_LIMITS,
): string | null => {
  const mediaType = normalizedMediaType(file.type)
  if (!SUPPORTED_IMAGE_MEDIA_TYPES.has(mediaType)) {
    return `不支持的图片类型：${file.name}（仅支持 PNG、JPEG、WebP 和 GIF）`
  }
  if (file.size <= 0) {
    return `图片内容为空：${file.name}`
  }
  if (file.size > limits.maxBytes) {
    return `图片过大：${file.name}（单张最大 ${formatImageLimit(limits.maxBytes)}）`
  }
  return null
}

export const validateChatImage = (
  image: ChatImage,
  limits: Readonly<ImageAttachmentLimits> = DEFAULT_IMAGE_ATTACHMENT_LIMITS,
): ChatImageValidationResult => {
  const name = image.name.trim() || '未命名图片'
  const declaredMediaType = normalizedMediaType(image.media_type)
  if (!SUPPORTED_IMAGE_MEDIA_TYPES.has(declaredMediaType)) {
    return {
      error: `不支持的图片类型：${name}（仅支持 PNG、JPEG、WebP 和 GIF）`,
      sizeBytes: 0,
    }
  }

  const dataUrl = inspectImageDataUrl(image.data_url.trim())
  if (!dataUrl) {
    return { error: `图片数据无效或已损坏：${name}`, sizeBytes: 0 }
  }
  if (!SUPPORTED_IMAGE_MEDIA_TYPES.has(dataUrl.mediaType)) {
    return {
      error: `不支持的图片 data URL 类型：${name}`,
      sizeBytes: dataUrl.sizeBytes,
    }
  }
  if (declaredMediaType !== dataUrl.mediaType) {
    return {
      error: `图片媒体类型与 data URL 不一致：${name}`,
      sizeBytes: dataUrl.sizeBytes,
    }
  }
  if (dataUrl.sizeBytes <= 0) {
    return { error: `图片内容为空：${name}`, sizeBytes: 0 }
  }
  if (dataUrl.sizeBytes > limits.maxBytes) {
    return {
      error: `图片过大：${name}（单张最大 ${formatImageLimit(limits.maxBytes)}）`,
      sizeBytes: dataUrl.sizeBytes,
    }
  }
  return { error: null, sizeBytes: dataUrl.sizeBytes }
}

const SUPPORTED_ATTACHMENT_EXTENSIONS = new Set([
  '.pdf',
  '.doc',
  '.docx',
  '.txt',
  '.md',
  '.csv',
  '.tsv',
  '.json',
  '.xls',
  '.xlsx',
])

const WORKFLOW_DATA_FILE_EXTENSIONS = new Set(['.csv', '.tsv', '.json', '.xls', '.xlsx'])

const MAX_ATTACHMENT_FILE_SIZE_BYTES = 5 * 1024 * 1024
export const MAX_ATTACHMENT_COUNT = 6

export interface ComposerSuggestion {
  id: string
  trigger: '/' | '@'
  label: string
  description: string
  insertText: string
}

export interface TriggerRange {
  start: number
  end: number
}

export interface ResearchRequestConfig {
  searchDepth: 'basic' | 'advanced'
  maxResults: number
  maxRounds: number
  maxResultsPerQuery: number
}

export const SLASH_TEMPLATES: ComposerSuggestion[] = [
  {
    id: 'summary',
    trigger: '/',
    label: 'summary',
    description: '总结当前问题并给出关键结论',
    insertText: '请基于上下文给出结构化总结：\n1. 关键结论\n2. 证据与依据\n3. 下一步建议\n',
  },
  {
    id: 'plan',
    trigger: '/',
    label: 'plan',
    description: '输出可执行计划',
    insertText: '请给出一个可执行计划（阶段、里程碑、风险、验收标准）。\n',
  },
  {
    id: 'review',
    trigger: '/',
    label: 'review',
    description: '代码评审模板（风险优先）',
    insertText: '请进行代码评审，按严重级别列出问题、影响范围和修复建议。\n',
  },
  {
    id: 'rewrite',
    trigger: '/',
    label: 'rewrite',
    description: '改写为更清晰版本',
    insertText: '请在保持原意的前提下，改写为更清晰、简洁、专业的版本。\n',
  },
  {
    id: 'translate',
    trigger: '/',
    label: 'translate',
    description: '中英互译模板',
    insertText: '请将下面内容翻译成英文，并保持术语一致：\n',
  },
  {
    id: 'table',
    trigger: '/',
    label: 'table',
    description: '表格化对比输出',
    insertText: '请用 Markdown 表格输出对比：包含方案、优点、风险、适用场景、推荐结论。\n',
  },
]

const getFileExtension = (fileName: string): string => {
  const index = fileName.lastIndexOf('.')
  return index >= 0 ? fileName.slice(index).toLowerCase() : ''
}

export const formatFileSize = (sizeBytes: number): string => {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

export const validateAttachmentFile = (file: File): string | null => {
  const extension = getFileExtension(file.name)
  if (!SUPPORTED_ATTACHMENT_EXTENSIONS.has(extension)) {
    return `不支持的文件类型：${file.name}`
  }
  if (file.size > MAX_ATTACHMENT_FILE_SIZE_BYTES) {
    return `文件过大：${file.name}（最大 5 MB）`
  }
  return null
}

export const isWorkflowDataFile = (file: ChatFile): boolean => {
  const extension = getFileExtension(file.name)
  if (WORKFLOW_DATA_FILE_EXTENSIONS.has(extension)) return true

  const mediaType = file.media_type.toLowerCase()
  return (
    mediaType === 'text/csv' ||
    mediaType === 'text/tab-separated-values' ||
    mediaType === 'application/json' ||
    mediaType === 'application/vnd.ms-excel' ||
    mediaType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    mediaType.endsWith('+json')
  )
}

export const buildDataWorkflowPlan = (query: string): Array<Record<string, unknown>> => [
  {
    id: 'step-1',
    agent: 'data_analysis',
    task_type: 'data_analysis',
    description: query,
    input: query,
    status: 'pending',
    requires_approval: false,
    metadata: {
      source: 'composer_data_files',
    },
  },
  {
    id: 'step-2',
    agent: 'writing',
    task_type: 'writing',
    description: `Summarize the data analysis for: ${query}`,
    input: query,
    status: 'pending',
    requires_approval: false,
    metadata: {
      output: 'data_brief',
    },
  },
  {
    id: 'step-3',
    agent: 'review',
    task_type: 'review',
    description: `Review data quality and interpretation risks for: ${query}`,
    input: query,
    status: 'pending',
    requires_approval: false,
    metadata: {
      focus: 'data_quality_and_risk',
    },
  },
]

export const buildDeepResearchWorkflowPlan = (
  query: string,
  requestConfig: ResearchRequestConfig,
  sourceStrategy: ResearchSourceStrategy,
): Array<Record<string, unknown>> => [
  {
    id: 'step-1',
    agent: 'research',
    task_type: 'research',
    description: query,
    input: query,
    status: 'pending',
    requires_approval: false,
    metadata: {
      research_mode: 'deep',
      research_source_strategy: sourceStrategy,
      max_rounds: requestConfig.maxRounds,
      max_results_per_query: requestConfig.maxResultsPerQuery,
    },
  },
  {
    id: 'step-2',
    agent: 'writing',
    task_type: 'writing',
    description: `Draft a concise research brief for: ${query}`,
    input: query,
    status: 'pending',
    requires_approval: false,
    metadata: {
      output: 'research_brief',
    },
  },
  {
    id: 'step-3',
    agent: 'review',
    task_type: 'review',
    description: `Review evidence quality and risks for: ${query}`,
    input: query,
    status: 'pending',
    requires_approval: false,
    metadata: {
      focus: 'evidence_and_risk',
    },
  },
]

export const filesToChatImages = async (files: File[]): Promise<ChatImage[]> => {
  const error = files.map((file) => validateImageFile(file)).find(Boolean)
  if (error) throw new Error(error)

  return Promise.all(
    files.map(async (file) => ({
      name: file.name,
      media_type: normalizedMediaType(file.type),
      data_url: await readFileAsDataUrl(file),
    })),
  )
}

export const filesToChatFiles = async (files: File[]): Promise<ChatFile[]> =>
  Promise.all(
    files.map(async (file) => ({
      name: file.name,
      media_type: file.type || 'application/octet-stream',
      data_url: await readFileAsDataUrl(file),
      size_bytes: file.size,
    })),
  )

export const mergeComposerText = (currentText: string, incomingText: string): string => {
  const nextText = incomingText.trim()
  if (!nextText) return currentText
  if (!currentText.trim()) return nextText
  if (currentText.includes(nextText)) return currentText
  return `${currentText.replace(/\s+$/, '')}\n\n${nextText}`
}

export const buildAnswerGroupId = (preferredAnswerGroupId?: string | null): string =>
  preferredAnswerGroupId?.trim() ||
  (globalThis.crypto?.randomUUID?.() ?? `grp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)

export const classifyStreamFailure = (error: string) => {
  const normalizedError = error.trim() || 'Request failed while processing.'
  const isNetworkError = /failed to fetch|network|backend returned an empty response body/i.test(
    normalizedError,
  )
  const isTimeoutError = /timeout|timed out|504|超时/i.test(normalizedError)

  return {
    content: isNetworkError
      ? 'Network connection failed. Unable to reach the backend service.'
      : isTimeoutError
        ? 'The request timed out before the model finished responding.'
        : normalizedError,
    errorCode: isNetworkError ? 'NETWORK_ERROR' : isTimeoutError ? 'TIMEOUT' : 'REQUEST_FAILED',
    suggestion: isNetworkError || isTimeoutError
      ? undefined
      : 'Please adjust the message or attachments and try again.',
  }
}

const imageAttachmentKey = (image: ChatImage): string =>
  image.data_url

const fileAttachmentKey = (file: ChatFile): string =>
  [
    file.name,
    file.media_type,
    String(file.size_bytes),
    (file.data_url ?? '').slice(0, 64),
    (file.extracted_text ?? '').slice(0, 64),
  ].join('::')

export const mergeUniqueImages = (current: ChatImage[], incoming: ChatImage[]): ChatImage[] => {
  const seen = new Set(current.map(imageAttachmentKey))
  const merged = [...current]
  for (const image of incoming) {
    const key = imageAttachmentKey(image)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(image)
  }
  return merged
}

const sanitizeCurrentImages = (
  current: ChatImage[],
  limits: Readonly<ImageAttachmentLimits>,
): { error: string | null; images: ChatImage[]; totalBytes: number } => {
  const images: ChatImage[] = []
  const seen = new Set<string>()
  let error: string | null = null
  let totalBytes = 0

  for (const image of current) {
    const key = imageAttachmentKey(image)
    if (seen.has(key)) continue

    const validation = validateChatImage(image, limits)
    if (validation.error) {
      error ??= validation.error
      continue
    }
    if (images.length >= limits.maxCount) {
      error ??= `每条消息最多只能附加 ${limits.maxCount} 张图片。`
      continue
    }
    if (totalBytes + validation.sizeBytes > limits.maxTotalBytes) {
      error ??= `图片总大小不能超过 ${formatImageLimit(limits.maxTotalBytes)}。`
      continue
    }

    seen.add(key)
    images.push(image)
    totalBytes += validation.sizeBytes
  }

  return { error, images, totalBytes }
}

export const mergeImagesWithinLimits = (
  current: ChatImage[],
  incoming: ChatImage[],
  limits: Readonly<ImageAttachmentLimits> = DEFAULT_IMAGE_ATTACHMENT_LIMITS,
): ChatImageMergeResult => {
  const sanitized = sanitizeCurrentImages(current, limits)
  if (sanitized.error) {
    return { error: sanitized.error, images: sanitized.images }
  }

  const seen = new Set(sanitized.images.map(imageAttachmentKey))
  const nextImages: ChatImage[] = []
  let nextBytes = 0

  for (const image of incoming) {
    const key = imageAttachmentKey(image)
    if (seen.has(key)) continue

    const validation = validateChatImage(image, limits)
    if (validation.error) {
      return { error: validation.error, images: sanitized.images }
    }
    seen.add(key)
    nextImages.push(image)
    nextBytes += validation.sizeBytes
  }

  if (sanitized.images.length + nextImages.length > limits.maxCount) {
    return {
      error: `每条消息最多只能附加 ${limits.maxCount} 张图片。`,
      images: sanitized.images,
    }
  }
  if (sanitized.totalBytes + nextBytes > limits.maxTotalBytes) {
    return {
      error: `图片总大小不能超过 ${formatImageLimit(limits.maxTotalBytes)}。`,
      images: sanitized.images,
    }
  }

  return { error: null, images: [...sanitized.images, ...nextImages] }
}

export const mergeUniqueFiles = (current: ChatFile[], incoming: ChatFile[]): ChatFile[] => {
  const seen = new Set(current.map(fileAttachmentKey))
  const merged = [...current]
  for (const file of incoming) {
    const key = fileAttachmentKey(file)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(file)
  }
  return merged
}
