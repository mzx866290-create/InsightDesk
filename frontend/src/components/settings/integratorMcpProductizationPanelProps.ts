import type { ComponentProps } from 'react'

import type { McpProductizationPanel } from './McpProductizationPanel'
import type { useMcpProductization } from './useMcpProductization'

export type McpProductizationPanelProps = ComponentProps<typeof McpProductizationPanel>

type McpProductizationController = ReturnType<typeof useMcpProductization>

type McpProductizationPanelState = Pick<
  McpProductizationController,
  | 'mcpMarketplaceSummary'
  | 'mcpMarketplaceCategories'
  | 'mcpMarketplaceCategoryId'
  | 'visibleMcpConnectors'
  | 'mcpConfig'
  | 'mcpRuntimeHealth'
  | 'mcpNotice'
  | 'mcpError'
  | 'mcpManifestText'
  | 'mcpLoading'
  | 'mcpPinging'
  | 'mcpHotUpdating'
  | 'mcpInstalling'
  | 'mcpManifestValidation'
  | 'handleMcpTemplateSelect'
  | 'setMcpManifestText'
  | 'setMcpMarketplaceCategoryId'
>

export interface BuildMcpProductizationPanelPropsParams {
  mcpProductization: McpProductizationPanelState
  onRefresh: () => void
  onRuntimePing: () => void
  onHotUpdate: () => void
  onManifestInstall: () => void
}

export function buildMcpProductizationPanelProps({
  mcpProductization,
  onRefresh,
  onRuntimePing,
  onHotUpdate,
  onManifestInstall,
}: BuildMcpProductizationPanelPropsParams): McpProductizationPanelProps {
  return {
    marketplaceSummary: mcpProductization.mcpMarketplaceSummary,
    marketplaceCategories: mcpProductization.mcpMarketplaceCategories,
    marketplaceCategoryId: mcpProductization.mcpMarketplaceCategoryId,
    visibleConnectors: mcpProductization.visibleMcpConnectors,
    fallbackSource: mcpProductization.mcpConfig?.source,
    runtimeHealth: mcpProductization.mcpRuntimeHealth,
    notice: mcpProductization.mcpNotice,
    error: mcpProductization.mcpError,
    manifestText: mcpProductization.mcpManifestText,
    loading: mcpProductization.mcpLoading,
    pinging: mcpProductization.mcpPinging,
    hotUpdating: mcpProductization.mcpHotUpdating,
    installing: mcpProductization.mcpInstalling,
    hotUpdateDisabled: !mcpProductization.mcpConfig,
    manifestValidation: mcpProductization.mcpManifestValidation,
    installDisabled:
      !mcpProductization.mcpManifestText.trim() ||
      mcpProductization.mcpManifestValidation.errors.length > 0 ||
      mcpProductization.mcpInstalling,
    onRefresh,
    onRuntimePing,
    onHotUpdate,
    onManifestInstall,
    onManifestTextChange: mcpProductization.setMcpManifestText,
    onTemplateSelect: mcpProductization.handleMcpTemplateSelect,
    onMarketplaceCategoryChange: mcpProductization.setMcpMarketplaceCategoryId,
  }
}
