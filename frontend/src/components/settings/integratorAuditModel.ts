const SENSITIVE_AUDIT_KEY_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|key)/i

export function formatAuditTime(timestamp: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) return '-'
  const millis = timestamp > 10_000_000_000 ? timestamp : timestamp * 1000
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(millis))
}

export function safeAuditDetails(details: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(details)
    .filter(([key]) => !SENSITIVE_AUDIT_KEY_PATTERN.test(key))
    .map(([key, value]) => {
      const rendered = typeof value === 'string' ? value : JSON.stringify(value)
      return [key, rendered ?? ''] as [string, string]
    })
    .filter(([, value]) => value && !/^https?:\/\//i.test(value) && !SENSITIVE_AUDIT_KEY_PATTERN.test(value))
    .slice(0, 4)
}
