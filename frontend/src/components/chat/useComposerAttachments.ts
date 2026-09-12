import { useRef, useState } from 'react'
import type { ChangeEvent, ClipboardEvent } from 'react'
import type { ChatFile, ChatImage } from '../../api/client'
import {
  MAX_ATTACHMENT_COUNT,
  MAX_IMAGE_COUNT,
  MAX_IMAGE_TOTAL_SIZE_BYTES,
  filesToChatFiles,
  filesToChatImages,
  mergeUniqueFiles,
  mergeImagesWithinLimits,
  validateAttachmentFile,
  validateChatImage,
  validateImageFile,
} from './messageInputUtils'

export const useComposerAttachments = () => {
  const [images, setImages] = useState<ChatImage[]>([])
  const [files, setFiles] = useState<ChatFile[]>([])
  const imagesRef = useRef<ChatImage[]>([])

  const showImageError = (message: string) => {
    window.alert(message)
  }

  const commitImages = (incoming: ChatImage[], replace = false): boolean => {
    const result = mergeImagesWithinLimits(replace ? [] : imagesRef.current, incoming)
    imagesRef.current = result.images
    setImages(result.images)
    if (result.error) {
      showImageError(result.error)
      return false
    }
    return true
  }

  const validateSelectedImages = (selectedFiles: File[]): string | null => {
    const fileError = selectedFiles.map((file) => validateImageFile(file)).find(Boolean)
    if (fileError) return fileError

    if (imagesRef.current.length + selectedFiles.length > MAX_IMAGE_COUNT) {
      return `每条消息最多只能附加 ${MAX_IMAGE_COUNT} 张图片。`
    }

    const currentBytes = imagesRef.current.reduce((total, image) => {
      const validation = validateChatImage(image)
      return total + (validation.error ? 0 : validation.sizeBytes)
    }, 0)
    const selectedBytes = selectedFiles.reduce((total, file) => total + file.size, 0)
    if (currentBytes + selectedBytes > MAX_IMAGE_TOTAL_SIZE_BYTES) {
      return `图片总大小不能超过 ${MAX_IMAGE_TOTAL_SIZE_BYTES / (1024 * 1024)} MB。`
    }
    return null
  }

  const mergeAttachments = (nextImages: ChatImage[], nextFiles: ChatFile[]) => {
    commitImages(nextImages)
    setFiles((current) => mergeUniqueFiles(current, nextFiles).slice(0, MAX_ATTACHMENT_COUNT))
  }

  const clearAttachments = () => {
    imagesRef.current = []
    setImages([])
    setFiles([])
  }

  const restoreAttachments = (nextImages: ChatImage[], nextFiles: ChatFile[]) => {
    commitImages(nextImages, true)
    setFiles(nextFiles)
  }

  const handleSelectImages = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? [])
    if (selectedFiles.length === 0) return

    const validationError = validateSelectedImages(selectedFiles)
    if (validationError) {
      showImageError(validationError)
      event.target.value = ''
      return
    }

    try {
      const nextImages = await filesToChatImages(selectedFiles)
      commitImages(nextImages)
    } catch (error) {
      console.error('Failed to load selected images', error)
      showImageError(error instanceof Error ? error.message : '图片读取失败，请重试。')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveImage = (index: number) => {
    const nextImages = imagesRef.current.filter((_, currentIndex) => currentIndex !== index)
    imagesRef.current = nextImages
    setImages(nextImages)
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

    const validationError = validateSelectedImages(imageFiles)
    if (validationError) {
      showImageError(validationError)
      return
    }

    try {
      const pastedImages = await filesToChatImages(imageFiles)
      commitImages(pastedImages)
    } catch (error) {
      console.error('Failed to paste images', error)
      showImageError(error instanceof Error ? error.message : '粘贴图片失败，请重试。')
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
