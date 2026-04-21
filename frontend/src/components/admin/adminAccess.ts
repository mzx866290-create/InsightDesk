export function isAdminAccessError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return (
    message.includes('API token') ||
    message.includes('API Token') ||
    message.includes('ADMIN_API_TOKEN') ||
    message.includes('admin token') ||
    message.includes('remote admin') ||
    message.includes('远程管理') ||
    message.includes('管理令牌')
  )
}
