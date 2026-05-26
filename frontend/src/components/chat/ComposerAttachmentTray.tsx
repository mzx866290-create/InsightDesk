import { Paperclip, X } from 'lucide-react'

import type { ChatFile, ChatImage } from '../../api/client'
import { formatFileSize } from './messageInputUtils'

interface ComposerAttachmentTrayProps {
  images: ChatImage[]
  files: ChatFile[]
  disabled: boolean
  onRemoveImage: (index: number) => void
  onRemoveFile: (index: number) => void
}

export function ComposerAttachmentTray({
  images,
  files,
  disabled,
  onRemoveImage,
  onRemoveFile,
}: ComposerAttachmentTrayProps) {
  if (images.length === 0 && files.length === 0) return null

  return (
    <>
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
                onClick={() => onRemoveImage(index)}
                disabled={disabled}
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
                onClick={() => onRemoveFile(index)}
                disabled={disabled}
                className="flex h-5 w-5 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title="Remove file"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
