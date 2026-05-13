import type React from 'react'
import type { McpConnector, Workspace } from '../../../api/client'
import {
  WORKSPACE_COLOR_LABELS,
  type WorkspaceDeckTheme,
} from './sidebarConstants'
import { WorkspacePresetFields } from './WorkspacePresetFields'

const WORKSPACE_COLOR_OPTIONS: Array<Workspace['color']> = [
  'blue',
  'green',
  'amber',
  'rose',
  'slate',
]

interface WorkspaceFormBaseProps {
  name: string
  color: Workspace['color']
  presetWebSearch: boolean
  presetKnowledgeBase: boolean
  presetMcpServers: string[]
  presetDeckTheme: WorkspaceDeckTheme
  presetDeckSlideCount: number
  availableMcpConnectors: McpConnector[]
  storePanelCount: number
  saving: boolean
  onNameChange: (name: string) => void
  onColorChange: (color: Workspace['color']) => void
  onPresetWebSearchChange: (enabled: boolean) => void
  onPresetKnowledgeBaseChange: (enabled: boolean) => void
  onPresetMcpServersChange: React.Dispatch<React.SetStateAction<string[]>>
  onPresetDeckThemeChange: (theme: WorkspaceDeckTheme) => void
  onPresetDeckSlideCountChange: (count: number) => void
  onCancel: () => void
  onSubmit: () => void | Promise<void>
}

interface WorkspaceCreateFormProps extends WorkspaceFormBaseProps {
  mode: 'create'
}

interface WorkspaceEditFormProps extends WorkspaceFormBaseProps {
  mode: 'edit'
  description: string
  onDescriptionChange: (description: string) => void
}

export type WorkspaceFormDialogProps = WorkspaceCreateFormProps | WorkspaceEditFormProps

export function WorkspaceFormDialog(props: WorkspaceFormDialogProps) {
  const isEditMode = props.mode === 'edit'
  const connectorKeyPrefix = isEditMode ? 'workspace-edit' : 'workspace-create'
  const presetDescription = isEditMode
    ? 'Saving here overwrites the workspace default panels with the current workbench snapshot.'
    : 'Save the current workbench snapshot: panels, tool toggles, and deck defaults.'
  const submitLabel = isEditMode
    ? props.saving ? 'Saving...' : 'Save'
    : props.saving ? 'Creating...' : 'Create'

  return (
    <div className="mt-3 space-y-2 rounded-xl border border-bg-border bg-bg-primary p-2.5">
      <input
        value={props.name}
        onChange={(event) => props.onNameChange(event.target.value)}
        placeholder="Workspace name"
        className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none placeholder:text-text-secondary"
      />
      {isEditMode && (
        <textarea
          value={props.description}
          onChange={(event) => props.onDescriptionChange(event.target.value)}
          placeholder="Workspace description"
          className="min-h-[72px] w-full resize-none rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none placeholder:text-text-secondary"
        />
      )}
      <select
        value={props.color}
        onChange={(event) => props.onColorChange(event.target.value as Workspace['color'])}
        className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none"
      >
        {WORKSPACE_COLOR_OPTIONS.map((color) => (
          <option key={color} value={color}>
            {WORKSPACE_COLOR_LABELS[color]}
          </option>
        ))}
      </select>
      <WorkspacePresetFields
        connectorKeyPrefix={connectorKeyPrefix}
        description={presetDescription}
        availableMcpConnectors={props.availableMcpConnectors}
        mcpServers={props.presetMcpServers}
        webSearchEnabled={props.presetWebSearch}
        knowledgeBaseEnabled={props.presetKnowledgeBase}
        deckTheme={props.presetDeckTheme}
        deckSlideCount={props.presetDeckSlideCount}
        storePanelCount={props.storePanelCount}
        onMcpServersChange={props.onPresetMcpServersChange}
        onWebSearchEnabledChange={props.onPresetWebSearchChange}
        onKnowledgeBaseEnabledChange={props.onPresetKnowledgeBaseChange}
        onDeckThemeChange={props.onPresetDeckThemeChange}
        onDeckSlideCountChange={props.onPresetDeckSlideCountChange}
      />
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={props.onCancel}
          className="rounded-lg px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
        >
          取消
        </button>
        <button
          type="button"
          onClick={() => {
            void props.onSubmit()
          }}
          disabled={props.saving}
          className="rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-primary transition-colors hover:border-accent-blue/40 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitLabel}
        </button>
      </div>
    </div>
  )
}
