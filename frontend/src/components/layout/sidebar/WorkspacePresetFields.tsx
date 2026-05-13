import type React from 'react'
import type { McpConnector } from '../../../api/client'
import {
  toggleConnectorSelection,
  type WorkspaceDeckTheme,
} from './sidebarConstants'

interface WorkspacePresetFieldsProps {
  connectorKeyPrefix: string
  description: string
  availableMcpConnectors: McpConnector[]
  mcpServers: string[]
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  deckTheme: WorkspaceDeckTheme
  deckSlideCount: number
  storePanelCount: number
  onMcpServersChange: React.Dispatch<React.SetStateAction<string[]>>
  onWebSearchEnabledChange: (enabled: boolean) => void
  onKnowledgeBaseEnabledChange: (enabled: boolean) => void
  onDeckThemeChange: (theme: WorkspaceDeckTheme) => void
  onDeckSlideCountChange: (count: number) => void
}

export function WorkspacePresetFields({
  connectorKeyPrefix,
  description,
  availableMcpConnectors,
  mcpServers,
  webSearchEnabled,
  knowledgeBaseEnabled,
  deckTheme,
  deckSlideCount,
  storePanelCount,
  onMcpServersChange,
  onWebSearchEnabledChange,
  onKnowledgeBaseEnabledChange,
  onDeckThemeChange,
  onDeckSlideCountChange,
}: WorkspacePresetFieldsProps) {
  return (
    <div className="rounded-lg border border-bg-border bg-bg-secondary/60 p-2.5 text-[11px] text-text-secondary">
      <div className="font-medium text-text-primary">Workspace preset</div>
      <div className="mt-1">{description}</div>
      <div className="mt-2 grid gap-2">
        <label className="flex items-center justify-between gap-3">
          <span>联网搜索</span>
          <input
            type="checkbox"
            checked={webSearchEnabled}
            onChange={(event) => onWebSearchEnabledChange(event.target.checked)}
          />
        </label>
        <label className="flex items-center justify-between gap-3">
          <span>Knowledge base</span>
          <input
            type="checkbox"
            checked={knowledgeBaseEnabled}
            onChange={(event) => onKnowledgeBaseEnabledChange(event.target.checked)}
          />
        </label>
        <div className="grid gap-1">
          <span>MCP Connectors</span>
          {availableMcpConnectors.length === 0 ? (
            <div className="rounded-lg border border-dashed border-bg-border bg-bg-primary px-2.5 py-2 text-[10px] text-text-secondary">
              No connectors available.
            </div>
          ) : (
            <div className="grid gap-1.5 rounded-lg border border-bg-border bg-bg-primary p-2">
              {availableMcpConnectors.map((connector) => (
                <label
                  key={`${connectorKeyPrefix}-${connector.name}`}
                  className="flex items-start justify-between gap-3 rounded-md px-2 py-1.5 hover:bg-bg-hover"
                >
                  <div className="min-w-0">
                    <div className="text-text-primary">{connector.label}</div>
                    <div className="text-[10px] leading-relaxed text-text-secondary">
                      {connector.description}
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={mcpServers.includes(connector.name)}
                    onChange={(event) =>
                      onMcpServersChange((current) =>
                        toggleConnectorSelection(current, connector.name, event.target.checked),
                      )
                    }
                  />
                </label>
              ))}
            </div>
          )}
        </div>
        <label className="grid gap-1">
          <span>Deck 主题</span>
          <select
            value={deckTheme}
            onChange={(event) => onDeckThemeChange(event.target.value as WorkspaceDeckTheme)}
            className="w-full rounded-lg border border-bg-border bg-bg-primary px-2.5 py-2 text-xs text-text-primary outline-none"
          >
            <option value="default">Default</option>
            <option value="midnight">Midnight Brief</option>
            <option value="sunrise">Sunrise Review</option>
          </select>
        </label>
        <label className="grid gap-1">
          <span>Deck 页数</span>
          <input
            type="number"
            min={4}
            max={10}
            value={deckSlideCount}
            onChange={(event) =>
              onDeckSlideCountChange(
                Math.max(4, Math.min(10, Number(event.target.value) || 8)),
              )
            }
            className="w-full rounded-lg border border-bg-border bg-bg-primary px-2.5 py-2 text-xs text-text-primary outline-none"
          />
        </label>
        <div>Current panel snapshot: {storePanelCount} panels</div>
      </div>
    </div>
  )
}
