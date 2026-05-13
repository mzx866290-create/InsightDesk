export const DEFAULT_SUPPORTED_CONNECTOR_TYPES = ['webhook', 'email', 'feishu', 'dingtalk']

export function supportedConnectorTypesOrDefault(types: string[]): string[] {
  return types.length > 0 ? types : DEFAULT_SUPPORTED_CONNECTOR_TYPES
}

export function clampConnectorSelectionIndex(index: number, connectorCount: number): number {
  return Math.max(0, Math.min(index, connectorCount - 1))
}

export function connectorActionErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : String(error || fallback)
}
