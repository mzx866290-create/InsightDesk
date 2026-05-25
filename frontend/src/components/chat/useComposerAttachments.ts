import { useState } from 'react'
import type { ChangeEvent, ClipboardEvent } from 'react'
import type { ChatFile, ChatImage } from '../../api/client'
import {
  MAX_ATTACHMENT_COUNT,
  filesToChatFiles,
  filesToChatImages,
  mergeUniqueFiles,
  mergeUniqueImages,
  validateAttachmentFile,
} from './messageInputUtils'

export const useComposerAttachments = () => {
  const [images, setImages] = useState<ChatImage[]>([])
  const [files, setFiles] = useState<ChatFile[]>([])

  const mergeAttachments = (nextImages: ChatImage[], nextFiles: ChatFile[]) => {
    setImages((current) => mergeUniqueImages(current, nextImages))
    setFiles((current) => mergeUniqueFiles(current, nextFiles).slice(0, MAX_ATTACHMENT_COUNT))
  }

  const clearAttachments = () => {
    setImages([])
    setFiles([])
  }

  const restoreAttachments = (nextImages: ChatImage[], nextFiles: ChatFile[]) => {
    setImages(nextImages)
    setFiles(nextFiles)
  }

  const handleSelectImages = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? [])
    if (selectedFiles.length === 0) return

    try {
      const nextImages = await filesToChatImages(selectedFiles)
      setImages((current) => [...current, ...nextImages])
    } catch (error) {
      console.error('Failed to load selected images', error)
      window.alert('图片读取失败，请重试。')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveImage = (index: number) => {
    setImages((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }

  const handleSelectFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? [])
    if (selectedFiles.length === 0) return

    const errors = selectedFiles
      .map((file) => validateAttachmentFile(file))
      .filter((error): error is string => Boolean(error))
    const validFiles = selectedFiles.filter((file) => validateAttachmentFile(file) === null)

    if (validFiles.length === 0) {
      window.alert(errors[0] ?? '没有选择支持的文件类型。')
      event.target.value = ''
      return
    }

    if (files.length + validFiles.length > MAX_ATTACHMENT_COUNT) {
      window.alert(`每条消息最多附加 ${MAX_ATTACHMENT_COUNT} 个文件。`)
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
      window.alert('文件读取失败，请重试。')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveFile = (index: number) => {
    setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }

  const handlePaste = async (event: ClipboardEvent<HTMLTextAreaElement>) => {
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
      window.alert('粘贴图片失败，请重试。')
    }
  }

  return {
    images,
    files,
    mergeAttachments,
    clearAttachments,
    restoreAttachments,
    handleSelectImages,
    handleRemoveImage,
    handleSelectFiles,
    handleRemoveFile,
    handlePaste,
  }
}
