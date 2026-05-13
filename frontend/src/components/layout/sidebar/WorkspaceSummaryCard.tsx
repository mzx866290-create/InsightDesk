import type { Workspace, WorkspacePreset } from '../../../api/client'
import {
  DEFAULT_WORKSPACE_ID,
  WORKSPACE_COLOR_LABELS,
  WORKSPACE_COLOR_TONES,
  WORKSPACE_DECK_THEME_LABELS,
} from './sidebarConstants'

interface WorkspaceSummaryCardProps {
  workspace: Workspace
  preset?: WorkspacePreset
  connectorSummary: string
  panelSummary: string
}

export function WorkspaceSummaryCard({
  workspace,
  preset,
  connectorSummary,
  panelSummary,
}: WorkspaceSummaryCardProps) {
  return (
    <div className="mt-3 rounded-xl border border-bg-border bg-bg-primary px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${WORKSPACE_COLOR_TONES[workspace.color]}`}
          >
            {WORKSPACE_COLOR_LABELS[workspace.color]}
          </span>
          <div className="truncate text-xs font-medium text-text-primary">
            {workspace.name}
          </div>
        </div>
        <span className="shrink-0 text-[10px] text-text-secondary">
          {workspace.session_count} sessions
        </span>
      </div>
      {workspace.description && (
        <div className="mt-1.5 text-[11px] leading-relaxed text-text-secondary">
          {workspace.description}
        </div>
      )}
      <div className="mt-2 grid gap-1 text-[10px] text-text-secondary">
        <div>
          Tools: {preset?.tool_config.web_search_enabled ? 'Web on' : 'Web off'} /{' '}
          {preset?.tool_config.knowledge_base_enabled === false ? 'KB off' : 'KB on'}
        </div>
        <div>Connectors: {connectorSummary}</div>
        <div>
          Panels: {preset?.default_panels.length ?? 0}
          {panelSummary ? ` / ${panelSummary}` : ''}
        </div>
        <div>
          Deck: {WORKSPACE_DECK_THEME_LABELS[preset?.output_preset.deck_theme ?? 'default']} /{' '}
          {preset?.output_preset.target_slide_count ?? 8} slides
        </div>
      </div>
      {workspace.workspace_id === DEFAULT_WORKSPACE_ID && (
        <div className="mt-1.5 text-[10px] text-text-secondary">
          Default workspace is protected and cannot be deleted.
        </div>
      )}
    </div>
  )
}
