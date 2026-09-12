/**
 * 知识库管理弹窗
 * P0 功能：文档列表、上传进度、删除确认、检索测试
 * 根据 20260413plan.md P0 改进项实施
 */

import React, { useCallback, useEffect, useState } from 'react'
import { AdminTokenPanel } from '../admin/AdminTokenPanel'
import { Modal } from '../ui/Modal'
import {
  getAdminApiToken,
  saveAdminApiToken,
} from '../../api/client'
import { KbMonitorPanel } from './KbMonitorPanel'
import { KnowledgeBaseDocumentsTab } from './KnowledgeBaseDocumentsTab'
import { KnowledgeBaseTabs } from './KnowledgeBaseTabs'
import { KnowledgeBaseUploadTab } from './KnowledgeBaseUploadTab'
import { type TabKey } from './knowledgeBaseModalModel'
import { useKbMonitor } from './useKbMonitor'

// ── 主组件 ───────────────────────────────────────────

interface KnowledgeBaseModalProps {
  open: boolean
  onClose: () => void
}

export const KnowledgeBaseModal: React.FC<KnowledgeBaseModalProps> = ({ open, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabKey>('documents')
  const [refreshKey, setRefreshKey] = useState(0)
  const [adminToken, setAdminToken] = useState('')
  const [adminTokenSaved, setAdminTokenSaved] = useState(false)
  const [adminAccessError, setAdminAccessError] = useState<string | null>(null)

  const handleDataChanged = useCallback(() => setRefreshKey((key) => key + 1), [])
  const kbMonitor = useKbMonitor({
    enabled: open && activeTab === 'monitor',
    onKnowledgeBasesChanged: handleDataChanged,
  })

  useEffect(() => {
    if (!open) return
    setAdminToken(getAdminApiToken())
    setAdminTokenSaved(false)
    setAdminAccessError(null)
  }, [open])

  const handleSaveAdminToken = () => {
    const normalized = adminToken.trim()
    saveAdminApiToken(normalized)
    setAdminToken(normalized)
    setAdminTokenSaved(true)
    setAdminAccessError(null)
    setRefreshKey((key) => key + 1)
    if (activeTab === 'monitor') {
      void kbMonitor.refreshCurrent()
    }
    window.setTimeout(() => setAdminTokenSaved(false), 2500)
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="知识库管理"
      width={activeTab === 'monitor' ? 'max-w-4xl' : 'max-w-2xl'}
    >
      <AdminTokenPanel
        token={adminToken}
        saved={adminTokenSaved}
        error={adminAccessError}
        title="Remote API Token"
        placeholder="Enter API token"
        description="远程访问知识库管理接口时需要。可在这里直接保存后刷新当前知识库视图。"
        onTokenChange={setAdminToken}
        onSave={handleSaveAdminToken}
        onClear={() => {
          setAdminToken('')
          saveAdminApiToken('')
          setAdminTokenSaved(false)
          setAdminAccessError(null)
          setRefreshKey((key) => key + 1)
          if (activeTab === 'monitor') {
            void kbMonitor.refreshCurrent()
          }
        }}
      />

      <KnowledgeBaseTabs activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Tab 内容 */}
      {activeTab === 'documents' && (
        <KnowledgeBaseDocumentsTab
          key={`docs-${refreshKey}`}
          onDeleted={handleDataChanged}
          onAdminAccessError={setAdminAccessError}
        />
      )}
      {activeTab === 'upload' && (
        <KnowledgeBaseUploadTab onUploaded={handleDataChanged} onAdminAccessError={setAdminAccessError} />
      )}
      {activeTab === 'monitor' && <KbMonitorPanel monitor={kbMonitor} />}
    </Modal>
  )
}
