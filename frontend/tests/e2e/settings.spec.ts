import { expect, test, openAdvancedSettings, openKnowledgeBaseMonitor } from './support/testHarness'

import { mockSecurityAuditFailure } from './support/mockApi'

test('manages a cloud model profile from settings', async ({ page }) => {
  const profileName = 'OpenRouter QA Profile'
  const initialApiKey = 'sk-initial-123'
  const rotatedApiKey = 'sk-rotated-456'

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()

  await page.getByTestId('settings-cloud-profile-name-input').fill(profileName)
  await page.getByTestId('settings-cloud-profile-api-key-input').fill(initialApiKey)
  await page.getByTestId('settings-cloud-profile-save').click()

  const profileList = page.getByTestId('settings-cloud-profile-list')
  const profileCard = profileList.locator(
    `[data-testid="settings-cloud-profile-card"][data-profile-name="${profileName}"]`,
  )

  await expect(profileCard).toContainText(profileName)
  await expect(profileCard.getByTestId('settings-cloud-profile-clear')).toBeVisible()

  await profileCard.getByTestId('settings-cloud-profile-edit').click()
  await expect(page.getByTestId('settings-cloud-profile-clear-editor')).toBeVisible()

  await page.getByTestId('settings-cloud-profile-api-key-input').fill(rotatedApiKey)
  await page.getByTestId('settings-cloud-profile-save').click()

  await expect(profileCard.getByTestId('settings-cloud-profile-clear')).toBeVisible()

  await profileCard.getByTestId('settings-cloud-profile-clear').click()
  await expect(profileCard.getByTestId('settings-cloud-profile-clear')).toHaveCount(0)

  await profileCard.getByTestId('settings-cloud-profile-delete').click()
  await expect(profileCard).toHaveCount(0)
})

test('keeps advanced settings collapsed until explicitly opened', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()

  const advancedToggle = page.getByTestId('settings-advanced-toggle')
  await expect(advancedToggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByTestId('settings-tab-general')).toBeVisible()
  await expect(page.getByTestId('settings-tab-documents')).toBeVisible()
  await expect(page.getByTestId('settings-tab-roles')).toHaveCount(0)
  await expect(page.getByTestId('settings-tab-integrations')).toHaveCount(0)

  await openAdvancedSettings(page)

  await expect(page.getByTestId('settings-tab-roles')).toBeVisible()
  await expect(page.getByTestId('settings-tab-integrations')).toBeVisible()
})

test('shows the agent catalog productization panel', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-agent_catalog').click()

  await expect(page.getByTestId('settings-agent-catalog-panel')).toBeVisible()
  await expect(page.getByTestId('settings-agent-catalog-summary')).toContainText('Plugins:')
  await expect(page.getByRole('heading', { name: 'support_triage' })).toBeVisible()
})

test('shows the delivery template catalog panel', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-delivery_templates').click()

  await expect(page.getByTestId('settings-delivery-template-catalog-panel')).toBeVisible()
  await expect(page.getByTestId('settings-delivery-template-summary')).toContainText('Decks:')
  await expect(page.getByRole('heading', { name: 'Board Deck' })).toBeVisible()
})

test('uploads a document and refreshes ingestion stats from settings', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-documents').click()

  await expect(page.getByTestId('settings-documents-panel')).toBeVisible()

  const uploadResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/documents/upload'),
  )
  await page
    .getByTestId('settings-documents-upload-input')
    .setInputFiles({
      name: 'ops-upload.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# Ops Upload\n\nSynthetic E2E document.'),
    })

  const uploadResponse = await uploadResponsePromise
  expect(uploadResponse.ok()).toBeTruthy()
  await expect(page.getByTestId('settings-documents-upload-result')).toHaveAttribute('data-status', 'success')
  await expect(page.getByTestId('settings-documents-upload-result')).toContainText('task-document-upload')
  await expect(page.getByTestId('settings-documents-upload-progress')).toBeVisible()

  const statsResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/documents/stats'),
  )
  await page.getByTestId('settings-documents-stats-refresh').click()

  const statsResponse = await statsResponsePromise
  expect(statsResponse.ok()).toBeTruthy()
  await expect(page.getByTestId('settings-documents-stats')).toBeVisible()
  await expect(page.getByTestId('settings-documents-stats-status')).toHaveText('ready')
  await expect(page.getByTestId('settings-documents-stats-total-docs')).toHaveText('4')
  await expect(page.getByTestId('settings-documents-stats-store-path')).toContainText('mock://knowledge-base/faiss')
})

test('shows knowledge base health and refreshes filtered chunks from settings', async ({ page }) => {
  await openKnowledgeBaseMonitor(page)

  await expect(page.getByTestId('settings-kb-health-summary')).toBeVisible()
  await expect(page.getByTestId('settings-kb-health-total-chunks')).toHaveText('3')

  await page.getByTestId('settings-kb-documents-toggle').click()
  await expect(page.getByTestId('settings-kb-documents-list')).toContainText('ops-handbook.md')

  const chunkList = page.getByTestId('settings-kb-chunk-list')
  await expect(chunkList.getByTestId('settings-kb-chunk-item')).toHaveCount(3)

  const filteredChunksResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/knowledge-base/chunks') &&
      response.url().includes('query=security'),
  )
  await page.getByTestId('settings-kb-chunk-query').fill('security')
  await page.getByTestId('settings-kb-chunk-search').click()

  const filteredChunksResponse = await filteredChunksResponsePromise
  expect(filteredChunksResponse.ok()).toBeTruthy()
  await expect(chunkList.getByTestId('settings-kb-chunk-item')).toHaveCount(1)
  await expect(chunkList).toContainText('incident-playbook.md')

  const refreshHealthResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/knowledge-base/health'),
  )
  const refreshChunksResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/knowledge-base/chunks') &&
      response.url().includes('query=security'),
  )
  await page.getByTestId('settings-kb-refresh').click()

  const [refreshHealthResponse, refreshChunksResponse] = await Promise.all([
    refreshHealthResponsePromise,
    refreshChunksResponsePromise,
  ])
  expect(refreshHealthResponse.ok()).toBeTruthy()
  expect(refreshChunksResponse.ok()).toBeTruthy()
  await expect(chunkList.getByTestId('settings-kb-chunk-item')).toHaveCount(1)
})

test('runs knowledge base retrieval diagnostics from settings', async ({ page }) => {
  await openKnowledgeBaseMonitor(page)

  await page.getByTestId('settings-kb-retrieval-mode').selectOption('hybrid')
  await page.getByTestId('settings-kb-retrieval-rerank').check()
  await page.getByTestId('settings-kb-retrieval-search-k').fill('4')
  await page.getByTestId('settings-kb-retrieval-fetch-k').fill('8')

  const retrievalResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/knowledge-base/test-retrieval'),
  )

  await page.getByTestId('settings-kb-retrieval-query').fill('incident escalation')
  await page.getByTestId('settings-kb-retrieval-run').click()

  const retrievalResponse = await retrievalResponsePromise
  expect(retrievalResponse.ok()).toBeTruthy()
  expect(retrievalResponse.request().postDataJSON()).toEqual({
    query: 'incident escalation',
    retrieval_mode: 'hybrid',
    search_k: 4,
    fetch_k: 8,
    use_rerank: true,
  })
  await expect(retrievalResponse.json()).resolves.toMatchObject({
    results_count: 2,
    search_mode: 'hybrid_rerank',
  })

  await expect(page.getByTestId('settings-kb-retrieval-result')).toBeVisible()
  await expect(page.getByTestId('settings-kb-retrieval-results-count')).toHaveText('2')
  await expect(page.getByTestId('settings-kb-retrieval-result')).toContainText('incident-playbook.md')
})

test('edits and deletes knowledge base chunks from settings', async ({ page }) => {
  await openKnowledgeBaseMonitor(page)

  const chunkRow = page.locator('[data-testid="settings-kb-chunk-item"][data-chunk-id="kb-chunk-1"]')
  await expect(chunkRow).toBeVisible()

  await chunkRow.getByTestId('settings-kb-chunk-edit').click()
  await chunkRow.getByTestId('settings-kb-chunk-edit-content').fill('')
  await chunkRow.getByTestId('settings-kb-chunk-edit-save').click()
  await expect(page.getByTestId('settings-kb-monitor-error')).toContainText('切片内容不能为空')

  const patchChunkResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      response.url().includes('/api/knowledge-base/chunks/kb-chunk-1'),
  )
  await chunkRow
    .getByTestId('settings-kb-chunk-edit-content')
    .fill('Updated incident escalation guidance for the operations team.')
  await chunkRow.getByTestId('settings-kb-chunk-edit-source').fill('ops-handbook-updated.md')
  await chunkRow.getByTestId('settings-kb-chunk-edit-save').click()

  const patchChunkResponse = await patchChunkResponsePromise
  expect(patchChunkResponse.ok()).toBeTruthy()
  expect(patchChunkResponse.request().postDataJSON()).toEqual({
    content: 'Updated incident escalation guidance for the operations team.',
    source: 'ops-handbook-updated.md',
  })
  await expect(
    page.locator('[data-testid="settings-kb-chunk-item"][data-chunk-id="kb-chunk-1"]'),
  ).toContainText('ops-handbook-updated.md')

  const deleteButton = page
    .locator('[data-testid="settings-kb-chunk-item"][data-chunk-id="kb-chunk-2"]')
    .getByTestId('settings-kb-chunk-delete')
  await deleteButton.click()
  await expect(deleteButton).toHaveAttribute('data-confirming', 'true')

  const deleteChunkResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'DELETE' &&
      response.url().includes('/api/knowledge-base/chunks/kb-chunk-2'),
  )
  await deleteButton.click()

  const deleteChunkResponse = await deleteChunkResponsePromise
  expect(deleteChunkResponse.ok()).toBeTruthy()
  await expect(page.locator('[data-testid="settings-kb-chunk-item"][data-chunk-id="kb-chunk-2"]')).toHaveCount(0)
  await expect(page.getByTestId('settings-kb-health-total-chunks')).toHaveText('2')
})

test('deletes the knowledge base only after confirmation from settings', async ({ page }) => {
  await openKnowledgeBaseMonitor(page)

  const deleteButton = page.getByTestId('settings-kb-delete')
  await deleteButton.click()
  await expect(deleteButton).toContainText('再次点击确认删除')

  const deleteKnowledgeBaseResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'DELETE' &&
      response.url().includes('/api/knowledge-base'),
  )
  await deleteButton.click()

  const deleteKnowledgeBaseResponse = await deleteKnowledgeBaseResponsePromise
  expect(deleteKnowledgeBaseResponse.ok()).toBeTruthy()
  await expect(page.getByTestId('settings-kb-empty-state')).toBeVisible()
  await expect(page.getByTestId('settings-kb-chunk-item')).toHaveCount(0)
})

test('saves SSO settings and starts the OIDC login flow from settings', async ({ page }) => {
  await page.route('https://idp.example.com/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/html; charset=utf-8',
      body: '<html><body>Mock IdP</body></html>',
    })
  })

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()

  await page.getByTestId('settings-sso-provider-input').selectOption('oidc')
  await page.getByTestId('settings-sso-issuer-url-input').fill('https://idp.example.com')
  await page
    .getByTestId('settings-sso-authorization-endpoint-input')
    .fill('https://idp.example.com/oauth2/v1/authorize')
  await page
    .getByTestId('settings-sso-token-endpoint-input')
    .fill('https://idp.example.com/oauth2/v1/token')
  await page
    .getByTestId('settings-sso-jwks-url-input')
    .fill('https://idp.example.com/oauth2/v1/keys')
  await page.getByTestId('settings-sso-client-id-input').fill('insightdesk')
  await page.getByTestId('settings-sso-client-secret-input').fill('sso-client-secret')
  await page.getByTestId('settings-sso-default-role-input').selectOption('admin')
  await page.getByTestId('settings-sso-scopes-input').fill('openid email profile groups')
  await page.getByTestId('settings-sso-session-ttl-input').fill('7200')
  await page
    .getByTestId('settings-sso-allowed-domains-input')
    .fill('example.com, ops.example.com')

  const saveSsoResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      response.url().includes('/api/auth/sso/config'),
  )
  await page.getByTestId('settings-sso-save').click()

  const saveSsoResponse = await saveSsoResponsePromise
  expect(saveSsoResponse.ok()).toBeTruthy()
  expect(saveSsoResponse.request().postDataJSON()).toMatchObject({
    provider: 'oidc',
    issuer_url: 'https://idp.example.com',
    authorization_endpoint: 'https://idp.example.com/oauth2/v1/authorize',
    token_endpoint: 'https://idp.example.com/oauth2/v1/token',
    jwks_url: 'https://idp.example.com/oauth2/v1/keys',
    client_id: 'insightdesk',
    client_secret: 'sso-client-secret',
    clear_client_secret: false,
    default_role: 'admin',
    scopes: 'openid email profile groups',
    session_ttl_seconds: 7200,
    allowed_domains: 'example.com, ops.example.com',
  })

  await expect(page.getByTestId('settings-sso-status')).toBeVisible()
  await expect(page.getByTestId('settings-sso-login')).toBeEnabled()

  const loginRequest = page.waitForRequest(
    (request) =>
      request.method() === 'GET' &&
      request.url().includes('/api/auth/sso/login?response_mode=fragment'),
  )
  await page.getByTestId('settings-sso-login').click()
  await loginRequest
  await page.waitForURL(/https:\/\/idp\.example\.com\/oauth2\/v1\/authorize/)
})

test('shows SSO save and refresh failures from settings', async ({ page }) => {
  await page.goto('/')
  const initialSsoResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/auth/sso/config'),
  )
  await page.getByTestId('header-open-settings').click()
  await initialSsoResponsePromise

  await page.route('**/api/auth/sso/config', async (route) => {
    if (route.request().method() === 'PUT') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ detail: 'Mock SSO save failed' }),
      })
      return
    }
    await route.fallback()
  })

  const saveFailureResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      response.url().includes('/api/auth/sso/config'),
  )
  await page.getByTestId('settings-sso-provider-input').selectOption('oidc')
  await page.getByTestId('settings-sso-save').click()

  const saveFailureResponse = await saveFailureResponsePromise
  expect(saveFailureResponse.status()).toBe(500)
  await expect(page.getByTestId('settings-sso-error')).toContainText('Mock SSO save failed')

  await page.unroute('**/api/auth/sso/config')
  await page.route('**/api/auth/sso/config', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 503,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ detail: 'Mock SSO refresh failed' }),
      })
      return
    }
    await route.fallback()
  })

  const refreshFailureResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/auth/sso/config'),
  )
  await page.getByTestId('settings-sso-refresh').click()

  const refreshFailureResponse = await refreshFailureResponsePromise
  expect(refreshFailureResponse.status()).toBe(503)
  await expect(page.getByTestId('settings-sso-error')).toContainText('Mock SSO refresh failed')
})

test('shows SSO login start failures without leaving settings', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()

  await page.getByTestId('settings-sso-provider-input').selectOption('oidc')
  await page.getByTestId('settings-sso-issuer-url-input').fill('https://idp.example.com')
  await page
    .getByTestId('settings-sso-authorization-endpoint-input')
    .fill('https://idp.example.com/oauth2/v1/authorize')
  await page
    .getByTestId('settings-sso-token-endpoint-input')
    .fill('https://idp.example.com/oauth2/v1/token')
  await page
    .getByTestId('settings-sso-jwks-url-input')
    .fill('https://idp.example.com/oauth2/v1/keys')
  await page.getByTestId('settings-sso-client-id-input').fill('insightdesk')

  const saveSsoResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      response.url().includes('/api/auth/sso/config'),
  )
  await page.getByTestId('settings-sso-save').click()
  expect((await saveSsoResponsePromise).ok()).toBeTruthy()
  await expect(page.getByTestId('settings-sso-login')).toBeEnabled()

  await page.route('**/api/auth/sso/login?response_mode=fragment', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify({ detail: 'Mock SSO login failed' }),
    })
  })

  const loginFailureResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/auth/sso/login?response_mode=fragment'),
  )
  await page.getByTestId('settings-sso-login').click()

  const loginFailureResponse = await loginFailureResponsePromise
  expect(loginFailureResponse.status()).toBe(500)
  await expect(page.getByTestId('settings-sso-error')).toContainText('Mock SSO login failed')
  await expect(page).toHaveURL(/127\.0\.0\.1:4173/)
  await expect(page.getByTestId('settings-sso-login')).toBeVisible()
})

test('shows and clears trace events from settings operations tab', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-traces').click()

  await expect(page.getByTestId('settings-trace-panel')).toBeVisible()
  await expect(page.getByTestId('settings-trace-event-row')).toHaveCount(3)
  await expect(page.getByTestId('settings-trace-event-list')).toContainText('agent.workflow')
  await expect(page.getByTestId('settings-trace-event-list')).toContainText('tool.retrieval')
  await expect(page.getByTestId('settings-trace-event-list')).toContainText('Mock retrieval failed')

  await page.getByTestId('settings-trace-refresh').click()
  await expect(page.getByTestId('settings-trace-event-row')).toHaveCount(3)

  await page.getByTestId('settings-trace-filter-event').selectOption('error')
  await page.getByTestId('settings-trace-filter-name').fill('tool.retrieval')
  await page.getByTestId('settings-trace-apply-filters').click()
  await expect(page.getByTestId('settings-trace-filter-status')).toContainText('filtered')
  await expect(page.getByTestId('settings-trace-event-row')).toHaveCount(1)
  await expect(page.getByTestId('settings-trace-event-list')).toContainText('tool.retrieval')

  await page.getByTestId('settings-trace-reset-filters').click()
  await expect(page.getByTestId('settings-trace-filter-status')).toContainText('all')
  await expect(page.getByTestId('settings-trace-event-row')).toHaveCount(3)

  await page.getByTestId('settings-trace-clear').click()
  await expect(page.getByTestId('settings-trace-empty')).toBeVisible()
  await expect(page.getByTestId('settings-trace-event-row')).toHaveCount(0)
  await expect(page.getByTestId('settings-trace-message')).toContainText('Trace cleared')
})

test('shows security audit summary from settings audit tab', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-security_audit').click()

  await expect(page.getByTestId('settings-security-audit-summary-panel')).toBeVisible()
  await expect(page.getByTestId('settings-security-status')).toContainText('Blocked')
  await expect(page.getByTestId('settings-security-status')).toContainText('Weak')
  await expect(page.getByTestId('settings-security-status')).toContainText('Yes')
  await expect(page.getByTestId('settings-security-status')).toContainText('16')
  await expect(page.getByTestId('settings-security-audit-actions')).toContainText('remote_auth_guard')
  await expect(page.getByTestId('settings-security-audit-results')).toContainText('success')
  await expect(page.getByTestId('settings-security-audit-categories')).toContainText('auth')
  await expect(page.getByTestId('settings-security-audit-events')).toContainText('task_approval_batch_decision')
  await expect(page.getByTestId('settings-security-audit-events')).toContainText('total=2')

  await page
    .getByTestId('settings-security-audit-event-action-filter')
    .fill('task_approval_batch_decision')
  await page.getByTestId('settings-security-audit-event-apply-filters').click()
  await expect(page.getByTestId('settings-security-audit-event-row')).toHaveCount(1)
  await expect(page.getByTestId('settings-security-audit-events')).toContainText('task_approval_batch_decision')

  await page.getByTestId('settings-security-audit-event-action-filter').fill('')
  await page.getByTestId('settings-security-audit-event-category-filter').selectOption('access')
  await page.getByTestId('settings-security-audit-event-user-filter').fill('playwright-viewer')
  await page.getByTestId('settings-security-audit-event-apply-filters').click()
  await expect(page.getByTestId('settings-security-audit-event-row')).toHaveCount(1)
  await expect(page.getByTestId('settings-security-audit-events')).toContainText('resource_access_denied')
  await expect(page.getByTestId('settings-security-audit-events')).toContainText('playwright-viewer')

  await page.getByTestId('settings-security-audit-category').selectOption('access')
  await expect(page.getByTestId('settings-security-audit-actions')).toContainText('resource_access_denied')
  await expect(page.getByTestId('settings-security-audit-results')).toContainText('denied')
  await expect(page.getByTestId('settings-security-audit-categories')).toContainText('access')

  await page.getByTestId('settings-security-audit-retention-keep-latest').fill('2')
  await page.getByTestId('settings-security-audit-retention-preview').click()
  await expect(page.getByTestId('settings-security-audit-retention-result')).toContainText('Would delete')
  await expect(page.getByTestId('settings-security-audit-retention-result')).toContainText('remaining 1')

  const cleanupResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/security/audit-events/cleanup'),
  )
  await page.getByTestId('settings-security-audit-retention-cleanup').click()
  const cleanupResponse = await cleanupResponsePromise
  await expect(cleanupResponse.json()).resolves.toMatchObject({
    dry_run: false,
    keep_latest: 2,
    deleted_count: 7,
    remaining_count: 2,
  })
  await expect(page.getByTestId('settings-security-audit-retention-result')).toContainText('2')
})

test('keeps security status card selector stable after audit refresh failure', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-security_audit').click()

  const securityStatus = page.getByTestId('settings-security-status')
  await expect(page.getByTestId('settings-security-audit-summary-panel')).toBeVisible()
  await expect(securityStatus).toBeVisible()
  await expect(securityStatus).toContainText('Blocked')
  await expect(securityStatus).toContainText('Weak')

  await mockSecurityAuditFailure(page, 'summary', 'Mock security audit refresh failed')

  const refreshFailureResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/security/audit-summary'),
  )
  await page.getByTestId('settings-security-audit-refresh').click()

  const refreshFailureResponse = await refreshFailureResponsePromise
  expect(refreshFailureResponse.status()).toBe(500)
  await expect(page.getByTestId('settings-security-audit-error')).toContainText(
    'Mock security audit refresh failed',
  )
  await expect(securityStatus).toBeVisible()
  await expect(securityStatus).toContainText('Blocked')
  await expect(securityStatus).toContainText('Weak')
})

test('keeps security audit event request filters and row selector stable', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-security_audit').click()

  await expect(page.getByTestId('settings-security-audit-summary-panel')).toBeVisible()

  const eventFilterResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/security/audit-events') &&
      response.url().includes('action=resource_access_denied'),
  )
  await page
    .getByTestId('settings-security-audit-event-action-filter')
    .fill('resource_access_denied')
  await page.getByTestId('settings-security-audit-event-category-filter').selectOption('access')
  await page.getByTestId('settings-security-audit-event-user-filter').fill('playwright-viewer')
  await page.getByTestId('settings-security-audit-event-apply-filters').click()

  const eventFilterResponse = await eventFilterResponsePromise
  expect(eventFilterResponse.ok()).toBeTruthy()

  const eventFilterUrl = new URL(eventFilterResponse.url())
  expect(eventFilterUrl.searchParams.get('action')).toBe('resource_access_denied')
  expect(eventFilterUrl.searchParams.get('category')).toBe('access')
  expect(eventFilterUrl.searchParams.get('user_id')).toBe('playwright-viewer')

  const eventRows = page.getByTestId('settings-security-audit-event-row')
  await expect(eventRows).toHaveCount(1)
  await expect(eventRows.first()).toContainText('resource_access_denied')
  await expect(eventRows.first()).toContainText('playwright-viewer')
})

test('shows security audit summary failure from settings audit tab', async ({ page }) => {
  await mockSecurityAuditFailure(page, 'summary', 'Mock security audit summary failed')

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-security_audit').click()

  await expect(page.getByTestId('settings-security-audit-summary-panel')).toBeVisible()
  await expect(page.getByTestId('settings-security-audit-error')).toContainText(
    'Mock security audit summary failed',
  )
})

test('shows security audit events failure from settings audit tab', async ({ page }) => {
  await mockSecurityAuditFailure(page, 'events', 'Mock security audit events failed')

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-security_audit').click()

  await expect(page.getByTestId('settings-security-audit-summary-panel')).toBeVisible()
  await expect(page.getByTestId('settings-security-audit-event-error')).toContainText(
    'Mock security audit events failed',
  )
  await expect(page.getByTestId('settings-security-audit-empty')).toBeVisible()
})

test('shows security audit retention cleanup failure from settings audit tab', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-security_audit').click()

  await expect(page.getByTestId('settings-security-audit-summary-panel')).toBeVisible()
  await expect(page.getByTestId('settings-security-audit-event-row').first()).toBeVisible()
  await mockSecurityAuditFailure(page, 'cleanup', 'Mock security audit cleanup failed')

  await page.getByTestId('settings-security-audit-retention-cleanup').click()

  await expect(page.getByTestId('settings-security-audit-retention-error')).toContainText(
    'Mock security audit cleanup failed',
  )
})

test('approves and revokes MCP connector approvals from settings', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-mcp_approvals').click()

  await expect(page.getByTestId('settings-mcp-approvals-panel')).toBeVisible()
  const configEditor = page.getByTestId('settings-mcp-config-editor')
  await expect(page.getByTestId('settings-mcp-config-panel')).toBeVisible()
  await expect(configEditor).toHaveValue(/custom-crm/)

  const nextConfig = {
    ...JSON.parse(await configEditor.inputValue()),
    default_enabled: ['knowledge-base', 'custom-crm'],
    config_version: 'smoke-hot-reload',
  }
  const saveConfigResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      response.url().includes('/api/connectors/mcp/config'),
  )
  await configEditor.fill(JSON.stringify(nextConfig, null, 2))
  await page.getByTestId('settings-mcp-config-save').click()
  const saveConfigResponse = await saveConfigResponsePromise
  expect(saveConfigResponse.status()).toBe(200)
  await expect(saveConfigResponse.json()).resolves.toMatchObject({
    config: {
      config_version: 'smoke-hot-reload',
      default_enabled: ['knowledge-base', 'custom-crm'],
    },
  })
  await expect(page.getByTestId('settings-mcp-approvals-message')).toContainText('Config saved')
  await expect(configEditor).toHaveValue(/smoke-hot-reload/)

  const crmRow = page.locator('[data-testid="settings-mcp-approval-row"][data-connector-name="custom-crm"]')
  await expect(crmRow).toContainText('Custom CRM')
  await expect(page.getByTestId('settings-mcp-approve-custom-crm')).toBeEnabled()

  await page.getByTestId('settings-mcp-approve-custom-crm').click()
  await expect(page.getByTestId('settings-mcp-revoke-custom-crm')).toBeVisible()

  await page.getByTestId('settings-mcp-runtime-health-check').click()
  await expect(page.getByTestId('settings-mcp-runtime-health')).toBeVisible()
  await expect(page.getByTestId('settings-mcp-runtime-health-row')).toHaveCount(2)
  await expect(page.getByTestId('settings-mcp-runtime-health')).toContainText('crm_sync_preview')
  await expect(page.getByTestId('settings-mcp-runtime-health-history-row')).toHaveCount(3)
  await expect(page.getByTestId('settings-mcp-runtime-health-history')).toContainText('Runtime health history')
  await expect(page.getByTestId('settings-mcp-runtime-health-history')).toContainText('1 healthy / 1 unhealthy')
  await expect(page.getByTestId('settings-mcp-runtime-health-history')).toContainText('alerts 1')
  await expect(page.getByTestId('settings-mcp-runtime-health-history')).toContainText('Custom CRM')

  await page.getByTestId('settings-mcp-revoke-custom-crm').click()
  await expect(page.getByTestId('settings-mcp-approve-custom-crm')).toBeEnabled()
})
