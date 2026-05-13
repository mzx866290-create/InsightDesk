import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'

import { getTask, uploadDocuments, type TaskRecord } from '../../api/client'
import { isAdminAccessError } from '../admin/adminAccess'

interface UseKnowledgeBaseUploadControllerOptions {
  onUploaded?: () => void
  onAdminAccessError?: (message: string | null) => void
}

export interface UseKnowledgeBaseUploadControllerResult {
  dragging: boolean
  files: File[]
  uploading: boolean
  task: TaskRecord | null
  error: string | null
  setDragging: (dragging: boolean) => void
  addFiles: (newFiles: FileList | File[]) => void
  removeFile: (name: string) => void
  handleDrop: (event: DragEvent<HTMLElement>) => void
  handleUpload: () => Promise<void>
}

export function useKnowledgeBaseUploadController({
  onUploaded,
  onAdminAccessError,
}: UseKnowledgeBaseUploadControllerOptions = {}): UseKnowledgeBaseUploadControllerResult {
  const [dragging, setDragging] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [task, setTask] = useState<TaskRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearPolling = useCallback(() => {
    if (!pollRef.current) return
    clearTimeout(pollRef.current)
    pollRef.current = null
  }, [])

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const incomingFiles = Array.from(newFiles)
    if (!incomingFiles.length) return

    setFiles(prevFiles => {
      const existingNames = new Set(prevFiles.map(file => file.name))
      const filesToAdd = incomingFiles.filter(file => !existingNames.has(file.name))
      return filesToAdd.length ? [...prevFiles, ...filesToAdd] : prevFiles
    })
  }, [])

  const removeFile = useCallback((name: string) => {
    setFiles(prevFiles => prevFiles.filter(file => file.name !== name))
  }, [])

  const handleDrop = useCallback((event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setDragging(false)
    addFiles(event.dataTransfer.files)
  }, [addFiles])

  const startPolling = useCallback((taskId: string) => {
    clearPolling()

    const poll = async () => {
      try {
        const nextTask = await getTask(taskId)
        setTask(nextTask)

        if (nextTask.status === 'completed' || nextTask.status === 'failed') {
          pollRef.current = null
          setUploading(false)
          if (nextTask.status === 'completed') {
            setFiles([])
            onUploaded?.()
          }
          return
        }

        pollRef.current = setTimeout(poll, 1500)
      } catch {
        pollRef.current = null
        setUploading(false)
        setError('无法获取任务状态')
      }
    }

    pollRef.current = setTimeout(poll, 800)
  }, [clearPolling, onUploaded])

  useEffect(() => clearPolling, [clearPolling])

  const handleUpload = useCallback(async () => {
    if (!files.length) return

    setUploading(true)
    setError(null)
    setTask(null)

    try {
      const result = await uploadDocuments(files)
      startPolling(result.task_id)
      onAdminAccessError?.(null)
    } catch (uploadError: unknown) {
      setUploading(false)
      const message = uploadError instanceof Error ? uploadError.message : '上传失败'
      setError(message)
      if (isAdminAccessError(uploadError)) onAdminAccessError?.(message)
    }
  }, [files, onAdminAccessError, startPolling])

  return {
    dragging,
    files,
    uploading,
    task,
    error,
    setDragging,
    addFiles,
    removeFile,
    handleDrop,
    handleUpload,
  }
}
