import React from 'react'
import { Loader2, Upload } from 'lucide-react'

interface KnowledgeBaseUploadActionButtonProps {
  uploading: boolean
  disabled: boolean
  onClick: () => void | Promise<void>
}

export const KnowledgeBaseUploadActionButton: React.FC<KnowledgeBaseUploadActionButtonProps> = ({
  uploading,
  disabled,
  onClick,
}) => (
  <button
    data-testid="settings-kb-upload-submit"
    onClick={() => {
      void onClick()
    }}
    disabled={disabled}
    className="w-full py-2.5 rounded-xl text-sm font-medium bg-accent-blue text-white hover:bg-accent-blue/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
  >
    {uploading ? <><Loader2 size={14} className="animate-spin" />处理中...</> : <><Upload size={14} />上传并索引</>}
  </button>
)
