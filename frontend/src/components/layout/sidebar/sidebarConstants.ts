import type { Workspace } from '../../../api/client'

export type SessionViewMode = 'all' | 'favorite' | 'archived'
export type WorkspaceDeckTheme = NonNullable<Workspace['preset']>['output_preset']['deck_theme']

export const DEFAULT_WORKSPACE_ID = 'workspace-default'
export const DEFAULT_ENABLED_MCP_SERVERS: string[] = []

export const WORKSPACE_DECK_THEME_LABELS: Record<WorkspaceDeckTheme, string> = {
  default: '经典蓝图',
  midnight: 'Midnight Brief',
  sunrise: '晨曦回顾',
}

export const WORKSPACE_COLOR_TONES: Record<Workspace['color'], string> = {
  blue: 'bg-accent-blue/15 text-accent-blue',
  green: 'bg-accent-green/15 text-accent-green',
  amber: 'bg-amber-300/15 text-amber-300',
  rose: 'bg-rose-400/15 text-rose-300',
  slate: 'bg-slate-400/15 text-slate-300',
}

export const WORKSPACE_COLOR_LABELS: Record<Workspace['color'], string> = {
  blue: '蓝色',
  green: '绿色',
  amber: '琥珀',
  rose: '玫瑰',
  slate: '石板',
}

export function toggleConnectorSelection(
  current: string[],
  connectorName: string,
  enabled: boolean,
): string[] {
  if (enabled) {
    return Array.from(new Set([...current, connectorName]))
  }
  return current.filter((item) => item !== connectorName)
}
