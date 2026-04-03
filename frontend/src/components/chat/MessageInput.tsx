import React, { useRef, useState } from 'react'
import { Send, Globe, Square, Database, ImagePlus, Paperclip, X } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { streamChat, createSession as apiCreateSession } from '../../api/client'
import type { ChatFile, ChatImage, SSEChunk } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'

interface MessageInputProps {
  onStreamingChange: (panelId: string, streaming: boolean) => void
}

const readFileAsDataUrl = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error(`Failed to read file: ${file.name}`))
    reader.readAsDataURL(file)
  })

const SUPPORTED_ATTACHMENT_EXTENSIONS = new Set([
  '.pdf',
  '.doc',
  '.docx',
  '.txt',
  '.md',
  '.csv',
  '.xls',
  '.xlsx',
])

const MAX_ATTACHMENT_FILE_SIZE_BYTES = 5 * 1024 * 1024
const MAX_ATTACHMENT_COUNT = 6

const getFileExtension = (fileName: string): string => {
  const index = fileName.lastIndexOf('.')
  return index >= 0 ? fileName.slice(index).toLowerCase() : ''
}

const formatFileSize = (sizeBytes: number): string => {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

const validateAttachmentFile = (file: File): string | null => {
  const extension = getFileExtension(file.name)
  if (!SUPPORTED_ATTACHMENT_EXTENSIONS.has(extension)) {
    return `Unsupported file type: ${file.name}`
  }
  if (file.size > MAX_ATTACHMENT_FILE_SIZE_BYTES) {
    return `File is too large: ${file.name} (max 5 MB)`
  }
  return null
}

const filesToChatImages = async (files: File[]): Promise<ChatImage[]> =>
  Promise.all(
    files
      .filter((file) => file.type.startsWith('image/'))
      .map(async (file) => ({
        name: file.name,
        media_type: file.type || 'image/png',
        data_url: await readFileAsDataUrl(file),
      })),
  )

const filesToChatFiles = async (files: File[]): Promise<ChatFile[]> =>
  Promise.all(
    files.map(async (file) => ({
      name: file.name,
      media_type: file.type || 'application/octet-stream',
      data_url: await readFileAsDataUrl(file),
      size_bytes: file.size,
    })),
  )

export const MessageInput: React.FC<MessageInputProps> = ({ onStreamingChange }) => {
  const {
    panels,
    currentSessionId,
    webSearchEnabled,
    setWebSearchEnabled,
    knowledgeBaseEnabled,
    setKnowledgeBaseEnabled,
    addUserMessage,
    appendChunk,
    setAssistantMessage,
    setSources,
    setTaskId,
    addErrorMessage,
    addSession,
    setCurrentSession,
    updateSessionTitle,
    updateSession,
    sessions,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [images, setImages] = useState<ChatImage[]>([])
  const [files, setFiles] = useState<ChatFile[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const attachmentInputRef = useRef<HTMLInputElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const streamingMsgIds = useRef<Map<string, string>>(new Map())

  const adjustHeight = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 180)}px`
  }

  const resetComposer = () => {
    setInput('')
    setImages([])
    setFiles([])
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    if (imageInputRef.current) {
      imageInputRef.current.value = ''
    }
    if (attachmentInputRef.current) {
      attachmentInputRef.current.value = ''
    }
  }

  const handleSelectImages = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    if (files.length === 0) return

    try {
      const nextImages = await filesToChatImages(files)
      setImages((current) => [...current, ...nextImages])
    } catch (error) {
      console.error('Failed to load selected images', error)
      window.alert('Failed to read image, please try again.')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveImage = (index: number) => {
    setImages((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }

  const handleSelectFiles = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? [])
    if (selectedFiles.length === 0) return

    const errors = selectedFiles
      .map((file) => validateAttachmentFile(file))
      .filter((error): error is string => Boolean(error))
    const validFiles = selectedFiles.filter((file) => validateAttachmentFile(file) === null)

    if (validFiles.length === 0) {
      window.alert(errors[0] ?? 'No supported files were selected.')
      event.target.value = ''
      return
    }

    if (files.length + validFiles.length > MAX_ATTACHMENT_COUNT) {
      window.alert(`You can attach up to ${MAX_ATTACHMENT_COUNT} files per message.`)
      event.target.value = ''
      return
    }

    try {
      const nextFiles = await filesToChatFiles(validFiles)
      setFiles((current) => [...current, ...nextFiles])
      if (errors.length > 0) {
        window.alert(errors[0])
      }
    } catch (error) {
      console.error('Failed to load selected files', error)
      window.alert('Failed to read file, please try again.')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveFile = (index: number) => {
    setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }

  const handlePaste = async (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = Array.from(event.clipboardData?.items ?? [])
    const imageFiles = items
      .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
      .map((item) => item.getAsFile())
      .filter((file): file is File => file !== null)

    if (imageFiles.length === 0) return

    event.preventDefault()

    try {
      const pastedImages = await filesToChatImages(imageFiles)
      setImages((current) => [...current, ...pastedImages])
    } catch (error) {
      console.error('Failed to paste images', error)
      window.alert('Failed to paste image, please try again.')
    }
  }

  const handleStop = () => {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    panels.forEach((panel) => {
      const msgId = streamingMsgIds.current.get(panel.id)
      if (msgId) {
        setAssistantMessage(panel.id, msgId, '', false)
      }
      onStreamingChange(panel.id, false)
    })
    streamingMsgIds.current.clear()
  }

  const syncSessionMetaFromPanels = (sessionId: string) => {
    const now = Date.now() / 1000
    const firstPanel = useChatStore.getState().panels[0]
    const messageCount = firstPanel
      ? firstPanel.messages.filter((message) => message.role !== 'error').length
      : 0

    updateSession(sessionId, {
      updated_at: now,
      message_count: messageCount,
    })
  }

  const handleSend = async () => {
    const msg = input.trim()
    const pendingImages = [...images]
    const pendingFiles = [...files]
    if ((msg.length === 0 && pendingImages.length === 0 && pendingFiles.length === 0) || isLoading) return

    resetComposer()
    setIsLoading(true)

    let sessionId = currentSessionId
    const sessionTitleSeed =
      msg ||
      (pendingFiles.length > 0 ? pendingFiles[0].name : '') ||
      (pendingImages.length > 0 ? 'Image chat' : '')

    if (!sessionId) {
      try {
        const session = await apiCreateSession(sessionTitleSeed.slice(0, 40))
        sessionId = session.session_id
        setCurrentSession(sessionId)
        addSession({
          session_id: sessionId,
          title: session.title,
          created_at: Date.now() / 1000,
          updated_at: Date.now() / 1000,
          message_count: 0,
        })
      } catch (error) {
        console.error('Failed to create session', error)
        setIsLoading(false)
        return
      }
    }

    addUserMessage(msg, pendingImages, pendingFiles)
    syncSessionMetaFromPanels(sessionId)

    const currentSession = sessions.find((session) => session.session_id === sessionId)
    if (currentSession && currentSession.message_count === 0 && sessionTitleSeed) {
      updateSessionTitle(sessionId, sessionTitleSeed.slice(0, 40))
    }

    panels.forEach((panel) => onStreamingChange(panel.id, true))
    const assistantMsgIds = new Map<string, string>()
    panels.forEach((panel) => {
      const messageId = `assistant-${panel.id}-${Date.now()}`
      assistantMsgIds.set(panel.id, messageId)
      streamingMsgIds.current.set(panel.id, messageId)
    })

    const donePanels = new Set<string>()

    const controller = streamChat(
      sessionId,
      msg,
      panels.map((panel) => panel.modelConfig),
      webSearchEnabled,
      knowledgeBaseEnabled,
      pendingImages,
      pendingFiles,
      (chunk: SSEChunk) => {
        const msgId = assistantMsgIds.get(chunk.panel_id)
        if (!msgId) return

        if (chunk.type === 'chunk' && chunk.content) {
          appendChunk(chunk.panel_id, msgId, chunk.content)
        } else if (chunk.type === 'sources' && chunk.sources) {
          setSources(chunk.panel_id, msgId, chunk.sources)
        } else if (chunk.type === 'task_created' && chunk.task_id) {
          const taskStore = useTaskStore.getState()
          taskStore.addTask({
            task_id: chunk.task_id,
            task_type: chunk.task_type ?? 'task',
            status: 'pending',
            progress: 0,
            created_at: Date.now() / 1000,
            updated_at: Date.now() / 1000,
          })
          taskStore.startPolling(chunk.task_id)
          setTaskId(chunk.panel_id, msgId, chunk.task_id, chunk.task_type)
        } else if (chunk.type === 'done') {
          onStreamingChange(chunk.panel_id, false)
          donePanels.add(chunk.panel_id)
          if (donePanels.size === panels.length) {
            syncSessionMetaFromPanels(sessionId)
            setIsLoading(false)
          }
        } else if (chunk.type === 'error') {
          setAssistantMessage(chunk.panel_id, msgId, '', false)
          addErrorMessage(
            chunk.panel_id,
            chunk.content ?? 'Request failed while processing.',
            chunk.error_code,
            chunk.suggestion,
          )
          onStreamingChange(chunk.panel_id, false)
          donePanels.add(chunk.panel_id)
          if (donePanels.size === panels.length) {
            syncSessionMetaFromPanels(sessionId)
            setIsLoading(false)
          }
        }
      },
      () => {
        syncSessionMetaFromPanels(sessionId)
        setIsLoading(false)
        panels.forEach((panel) => onStreamingChange(panel.id, false))
        streamingMsgIds.current.clear()
      },
      (err) => {
        const normalizedError = err?.trim() || 'Request failed while processing.'
        const isNetworkError = /failed to fetch|network|backend returned an empty response body/i.test(
          normalizedError,
        )
        panels.forEach((panel) => {
          addErrorMessage(
            panel.id,
            isNetworkError
              ? 'Network connection failed. Unable to reach the backend service.'
              : normalizedError,
            isNetworkError ? 'NETWORK_ERROR' : 'REQUEST_FAILED',
            isNetworkError
              ? 'Please check the network connection and verify the backend is running.'
              : 'Please adjust the message or attachments and try again.',
          )
          onStreamingChange(panel.id, false)
        })
        syncSessionMetaFromPanels(sessionId)
        setIsLoading(false)
        streamingMsgIds.current.clear()
        console.error('Stream error:', err)
      },
    )

    abortControllerRef.current = controller
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSend()
    }
  }

  const canSend = input.trim().length > 0 || images.length > 0 || files.length > 0

  return (
    <div className="sticky bottom-0 z-10 shrink-0 border-t border-bg-border bg-bg-primary/95 px-4 py-3 backdrop-blur-sm">
      <div className="mx-auto max-w-4xl">
        {images.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {images.map((image, index) => (
              <div
                key={`${image.name}-${index}`}
                className="group relative overflow-hidden rounded-xl border border-bg-border bg-bg-secondary"
              >
                <img
                  src={image.data_url}
                  alt={image.name}
                  className="h-20 w-20 object-cover"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveImage(index)}
                  className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white opacity-90 transition-opacity group-hover:opacity-100"
                  title="Remove image"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        {files.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="group flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2 text-xs text-text-primary"
              >
                <Paperclip size={12} className="shrink-0 text-text-secondary" />
                <div className="flex min-w-0 flex-col">
                  <span className="max-w-[180px] truncate">{file.name}</span>
                  <span className="text-[10px] text-text-secondary">
                    {formatFileSize(file.size_bytes)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(index)}
                  className="flex h-5 w-5 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="Remove file"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="rounded-2xl border border-bg-border bg-bg-secondary px-4 py-3 transition-colors focus-within:border-accent-blue/50">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <textarea
              ref={textareaRef}
              className="min-h-[24px] max-h-[180px] w-full flex-1 resize-none bg-transparent text-sm leading-relaxed text-text-primary outline-none placeholder:text-text-secondary"
              placeholder="Type a message, upload files or images. Enter to send, Shift+Enter for newline."
              value={input}
              onChange={(event) => {
                setInput(event.target.value)
                adjustHeight()
              }}
              onPaste={(event) => {
                void handlePaste(event)
              }}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isLoading}
            />

            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(event) => {
                void handleSelectImages(event)
              }}
            />

            <input
              ref={attachmentInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.txt,.md,.csv,.xls,.xlsx"
              multiple
              className="hidden"
              onChange={(event) => {
                void handleSelectFiles(event)
              }}
            />

            <div className="flex flex-wrap items-center justify-end gap-2 sm:pb-0.5">
              <button
                type="button"
                onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors ${
                  webSearchEnabled
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
                title="Web search"
              >
                <Globe size={13} />
              </button>

              <button
                type="button"
                onClick={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors ${
                  knowledgeBaseEnabled
                    ? 'bg-accent-green/20 text-accent-green'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
                title="Knowledge base"
              >
                <Database size={13} />
              </button>

              <button
                type="button"
                onClick={() => attachmentInputRef.current?.click()}
                disabled={isLoading}
                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                title="Attach file"
              >
                <Paperclip size={13} />
              </button>

              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={isLoading}
                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                title="Upload image"
              >
                <ImagePlus size={13} />
              </button>

              {isLoading ? (
                <button
                  type="button"
                  onClick={handleStop}
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-red/20 text-accent-red transition-colors hover:bg-accent-red/30"
                  title="Stop generation"
                >
                  <Square size={13} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    void handleSend()
                  }}
                  disabled={!canSend}
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-blue text-white transition-colors hover:bg-accent-blue-hover disabled:cursor-not-allowed disabled:opacity-30"
                  title="Send"
                >
                  <Send size={13} />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="mt-2 flex items-center justify-center text-[10px] text-text-secondary/50">
          AI can make mistakes, so please verify important information.
        </div>
      </div>
    </div>
  )
}
