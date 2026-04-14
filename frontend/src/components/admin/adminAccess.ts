export function isAdminAccessError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return (
    message.includes('管理令牌') ||
    message.includes('ADMIN_API_TOKEN') ||
    message.includes('远程管理接口已禁用')
  )
}
