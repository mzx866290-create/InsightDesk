import React from 'react'

import { SettingsNavigation } from './SettingsNavigation'
import { SettingsModalContent } from './SettingsModalContent'
import { Modal } from '../ui/Modal'
import { useSettingsModalController } from './useSettingsModalController'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

const BUILTIN_TEMPLATES = [
  {
    name: '企业知识库助手',
    content: 'You are an enterprise knowledge base assistant. Use available tools to answer accurately and cite sources when possible.',
  },
  {
    name: '代码审查专家',
    content: 'You are a senior code review expert. Analyze quality, security, performance and maintainability, and provide concrete suggestions.',
  },
  {
    name: '文档写作助理',
    content: 'You are a professional writing assistant. Help the user produce clear, structured technical and business documents.',
  },
]

export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose }) => {
  const { modalTitle, modalWidth, navigationProps, contentProps } = useSettingsModalController({
    open,
    quickTemplates: BUILTIN_TEMPLATES,
  })

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={modalTitle}
      width={modalWidth}
    >
      <SettingsNavigation {...navigationProps} />
      <SettingsModalContent {...contentProps} />
    </Modal>
  )
}
