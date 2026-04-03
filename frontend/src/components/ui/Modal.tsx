import React, { useEffect } from 'react'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  width?: string
}

export const Modal: React.FC<ModalProps> = ({ open, onClose, title, children, width = 'max-w-lg' }) => {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (open) document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto p-2 sm:p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative z-10 flex min-h-full items-start justify-center sm:items-center"
      >
        <div
          className={`relative z-10 my-4 flex max-h-[calc(100vh-1rem)] max-h-[calc(100svh-1rem)] w-full flex-col overflow-hidden rounded-2xl border border-bg-border bg-bg-secondary shadow-2xl animate-fade-in sm:my-6 sm:max-h-[calc(100vh-2rem)] sm:max-h-[calc(100svh-2rem)] ${width}`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex shrink-0 items-center justify-between border-b border-bg-border px-4 py-3 sm:px-6 sm:py-4">
            <h2 className="text-base font-semibold text-text-primary">{title}</h2>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            >
              <X size={16} />
            </button>
          </div>
          <div className="min-h-0 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">{children}</div>
        </div>
      </div>
    </div>
  )
}
