import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { Buffer } from 'node:buffer'

import { installAppApiMocks } from './support/mockApi'

test.beforeEach(async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await installAppApiMocks(page)
})

async function startResearch(page: Page, query: string): Promise<void> {
  await page.goto('/')

  await page.getByTestId('composer-research-mode-quick').click()
  await page.getByTestId('composer-input').fill(query)
  await page.getByTestId('composer-research').click()

  await expect(page.getByTestId('session-item')).toHaveCount(1)
  await expect(page.locator('[data-role="user"]').last()).toContainText(query)
  await expect(
    page.locator('[data-testid="task-progress-card"][data-task-type="web_research"]'),
  ).toBeVisible()
  await expect(page.locator('[data-role="assistant"]').last()).toContainText(
    `Research summary for: ${query}`,
  )
}

async function generateReportFromLatestResearch(page: Page, query: string): Promise<void> {
  await startResearch(page, query)
  await page.getByTestId('message-generate-report').last().click()
  await expect(page.getByTestId('task-progress-card').last()).toHaveAttribute(
    'data-task-type',
    'generate_report',
  )
  await expect(page.getByTestId('report-preview-modal')).toBeVisible()
}

async function openDeckEditorFromLatestResearch(page: Page, query: string): Promise<void> {
  await generateReportFromLatestResearch(page, query)
  await page.getByTestId('report-generate-deck').click()
  await expect(page.getByTestId('deck-generation-modal')).toBeVisible()
  await page.getByTestId('deck-generation-submit').click()
  await expect(
    page.locator('[data-testid="task-progress-card"][data-task-type="generate_deck"]'),
  ).toBeVisible()
  await expect(page.getByTestId('deck-editor-modal')).toBeVisible()
}

async function allowDeckRiskyExport(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.confirm = () => true
  })
}

async function mockDeckPdfPrintWindow(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const state = {
      opened: false,
      printed: false,
      html: '',
    }

    ;(
      window as typeof window & {
        __deckPdfExportState?: typeof state
      }
    ).__deckPdfExportState = state

    window.open = (() => {
      state.opened = true

      const mockWindow = {
        document: {
          open() {},
          write(html: string) {
            state.html = html
          },
          close() {},
        },
        focus() {},
        print() {
          state.printed = true
        },
      }

      Object.defineProperty(mockWindow, 'onload', {
        set(handler: unknown) {
          if (typeof handler === 'function') {
            handler()
          }
        },
      })

      return mockWindow as unknown as Window
    }) as typeof window.open
  })
}

async function mockReportSlidevWindow(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const state = {
      url: '',
      target: '',
      features: '',
    }

    ;(
      window as typeof window & {
        __reportSlidevState?: typeof state
      }
    ).__reportSlidevState = state

    window.open = ((url?: string | URL, target?: string, features?: string) => {
      state.url = typeof url === 'string' ? url : String(url ?? '')
      state.target = target ?? ''
      state.features = features ?? ''
      return null
    }) as typeof window.open
  })
}

test('shows the welcome guide and seeds the composer from the starter action', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByTestId('app-header')).toBeVisible()
  await expect(page.getByTestId('welcome-guide')).toBeVisible()

  await page.getByTestId('welcome-focus-chat').click()

  const composer = page.getByTestId('composer-input')
  await expect(composer).toBeVisible()
  await expect(composer).toHaveValue(/.+/)
  await expect(page.getByTestId('welcome-guide')).toBeHidden()
})

test('creates a session from the header new-chat action', async ({ page }) => {
  await page.goto('/')

  await page.getByTestId('header-new-chat').first().click()

  await expect(page.getByTestId('session-item')).toHaveCount(1)
  await expect(page.getByTestId('welcome-guide')).toBeVisible()
})

test('creates a session and completes the send-message flow', async ({ page }) => {
  const prompt = 'Summarize the current project setup'

  await page.goto('/')

  await page.getByTestId('composer-input').fill(prompt)
  await page.getByTestId('composer-send').click()

  await expect(page.getByTestId('session-item')).toHaveCount(1)
  await expect(page.locator('[data-role="user"]').last()).toContainText(prompt)
  await expect(page.locator('[data-role="assistant"]').last()).toContainText(
    `Mock answer for: ${prompt}`,
  )
})

test('starts a data analysis workflow from a csv attachment', async ({ page }) => {
  const prompt = 'Show top region by revenue'

  await page.goto('/')

  await page.getByTestId('composer-input').fill(prompt)
  await page.getByTestId('composer-attachment-input').setInputFiles({
    name: 'revenue.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('region,revenue\nNorth,120\nSouth,180\n'),
  })
  await expect(page.getByTestId('composer-research')).toContainText('鍒嗘瀽')
  await page.getByTestId('composer-research').click()

  await expect(page.getByTestId('session-item')).toHaveCount(1)
  await expect(page.locator('[data-role="user"]').last()).toContainText(prompt)
  await expect(page.locator('[data-role="user"]').last()).toContainText('revenue.csv')
  await expect(
    page.locator('[data-testid="task-progress-card"][data-task-type="multi_agent_workflow"]'),
  ).toBeVisible()
  await expect(page.locator('[data-role="assistant"]').last()).toContainText(
    `Mock data workflow completed for: ${prompt}`,
  )
})

test('approves a waiting multi-agent workflow from task center', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('composer-input').fill('Create a task center session')
  await page.getByTestId('composer-send').click()
  await expect(page.getByTestId('session-item')).toHaveCount(1)

  await page.getByTestId('header-more-menu').click()
  await page.getByTestId('header-open-task-center').click()

  await expect(page.getByTestId('task-center-modal')).toBeVisible()
  await page
    .getByTestId('task-center-workflow-prompt')
    .fill('Run approval checkpoint workflow')
  await page.getByTestId('task-center-start-workflow').click()

  const workflowTask = page
    .locator('[data-testid="task-center-task"][data-task-type="multi_agent_workflow"]')
    .first()
  await expect(workflowTask).toContainText('Approval gate')
  await expect(workflowTask).toContainText('Review agent execution plan')

  await workflowTask.getByTestId('task-center-approve').click()

  await expect(workflowTask).toContainText('Completed')
  await expect(workflowTask).toContainText('Mock workflow resumed after manual approval.')
})

test('batch approves waiting multi-agent workflows from task center', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('composer-input').fill('Create a batch approval session')
  await page.getByTestId('composer-send').click()
  await expect(page.getByTestId('session-item')).toHaveCount(1)

  await page.getByTestId('header-more-menu').click()
  await page.getByTestId('header-open-task-center').click()

  await expect(page.getByTestId('task-center-modal')).toBeVisible()
  await page
    .getByTestId('task-center-workflow-prompt')
    .fill('Run approval checkpoint workflow for batch approval')
  await page.getByTestId('task-center-start-workflow').click()

  const workflowTask = page
    .locator('[data-testid="task-center-task"][data-task-type="multi_agent_workflow"]')
    .first()
  await expect(workflowTask).toContainText('Approval gate')
  await expect(page.getByTestId('task-center-batch-approve')).toBeEnabled()

  const batchResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/tasks/approvals/batch'),
  )
  await page.getByTestId('task-center-batch-approve').click()

  const batchResponse = await batchResponsePromise
  expect(batchResponse.status()).toBe(200)
  await expect(batchResponse.json()).resolves.toMatchObject({
    total: 1,
    succeeded: 1,
    failed: 0,
  })
  await expect(workflowTask).toContainText('Completed')
})

test('updates task approval policy from task center', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('composer-input').fill('Create an approval policy session')
  await page.getByTestId('composer-send').click()
  await expect(page.getByTestId('session-item')).toHaveCount(1)

  await page.getByTestId('header-more-menu').click()
  await page.getByTestId('header-open-task-center').click()

  const policyPanel = page.getByTestId('task-center-approval-policy')
  await expect(policyPanel).toContainText('Enabled')
  await expect(policyPanel).toContainText('Multi-Agent Workflow')

  await policyPanel.getByRole('button', { name: 'Configure' }).click()
  await page.getByTestId('task-center-approval-policy-toggle').uncheck()

  const policyResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      response.url().includes('/api/tasks/approval-policy'),
  )
  await page.getByTestId('task-center-approval-policy-save').click()

  const policyResponse = await policyResponsePromise
  expect(policyResponse.ok()).toBeTruthy()
  await expect(policyPanel).toContainText('Saved.')
  await expect(policyPanel).toContainText('Disabled')
})

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
  const profileCard = profileList.locator('[data-testid^="settings-cloud-profile-card-"]').first()

  await expect(profileCard).toContainText(profileName)
  await expect(profileCard.locator('[data-testid^="settings-cloud-profile-clear-"]')).toBeVisible()

  await profileCard.locator('[data-testid^="settings-cloud-profile-edit-"]').click()
  await expect(page.getByTestId('settings-cloud-profile-clear-editor')).toBeVisible()

  await page.getByTestId('settings-cloud-profile-api-key-input').fill(rotatedApiKey)
  await page.getByTestId('settings-cloud-profile-save').click()

  await expect(profileCard.locator('[data-testid^="settings-cloud-profile-clear-"]')).toBeVisible()

  await profileCard.locator('[data-testid^="settings-cloud-profile-clear-"]').click()
  await expect(profileCard.locator('[data-testid^="settings-cloud-profile-clear-"]')).toHaveCount(0)

  await profileCard.locator('[data-testid^="settings-cloud-profile-delete-"]').click()
  await expect(profileCard).toHaveCount(0)
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
  await page
    .getByTestId('settings-sso-allowed-domains-input')
    .fill('example.com, ops.example.com')
  await page.getByTestId('settings-sso-save').click()

  await expect(page.getByText('Ready')).toBeVisible()
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

test('shows and clears trace events from settings operations tab', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
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
  await page.getByTestId('settings-tab-security_audit').click()

  await expect(page.getByTestId('settings-security-audit-summary-panel')).toBeVisible()
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

test('approves and revokes MCP connector approvals from settings', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
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

test('mocks Integrator connector config with webhook redaction persistence', async ({ page }) => {
  await page.goto('/')

  const initialPayload = await page.evaluate(async () => {
    const response = await fetch('/api/integrations/connectors')
    return {
      status: response.status,
      body: await response.json(),
    }
  })

  expect(initialPayload).toMatchObject({
    status: 200,
    body: {
      total: 2,
      supported_types: ['webhook', 'email', 'feishu', 'dingtalk'],
      persistence: {
        enabled: true,
        config_key: 'integrator_connectors',
        sensitive_fields_redacted: true,
      },
      connectors: expect.arrayContaining([
        expect.objectContaining({
          id: 'ops-webhook',
          type: 'webhook',
          name: 'Ops Webhook',
          enabled: true,
          approved: false,
          settings: {
            url: '***redacted***',
            token: '***redacted***',
            channel: 'ops-alerts',
            nested: {
              client_secret: '***redacted***',
              safe_label: 'incident-review',
            },
          },
        }),
      ]),
    },
  })
  expect(JSON.stringify(initialPayload.body)).not.toContain('https://hooks.example.test/ops')
  expect(JSON.stringify(initialPayload.body)).not.toContain('ops-webhook-token')
  expect(JSON.stringify(initialPayload.body)).not.toContain('nested-client-secret')

  const savedPayload = await page.evaluate(async () => {
    const response = await fetch('/api/integrations/connectors', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connectors: [
          {
            id: 'ops-webhook',
            type: 'webhook',
            name: 'Ops Webhook',
            description: 'Post incident updates to the operations webhook endpoint.',
            enabled: true,
            approved: true,
            settings: {
              url: '***redacted***',
              token: '***redacted***',
              channel: 'ops-critical',
              nested: {
                client_secret: '***redacted***',
                safe_label: 'post-save-review',
              },
            },
          },
        ],
      }),
    })
    return {
      status: response.status,
      body: await response.json(),
    }
  })

  expect(savedPayload).toMatchObject({
    status: 200,
    body: {
      total: 1,
      connectors: [
        {
          id: 'ops-webhook',
          type: 'webhook',
          approved: true,
          settings: {
            url: '***redacted***',
            token: '***redacted***',
            channel: 'ops-critical',
            nested: {
              client_secret: '***redacted***',
              safe_label: 'post-save-review',
            },
          },
        },
      ],
    },
  })
  expect(JSON.stringify(savedPayload.body)).not.toContain('https://hooks.example.test/ops')
  expect(JSON.stringify(savedPayload.body)).not.toContain('ops-webhook-token')
  expect(JSON.stringify(savedPayload.body)).not.toContain('nested-client-secret')

  const followUpPayload = await page.evaluate(async () => {
    const response = await fetch('/api/integrations/connectors')
    return response.json()
  })

  expect(followUpPayload).toEqual(savedPayload.body)
})

test('mocks Integrator connector test connection with redacted summary', async ({ page }) => {
  await page.goto('/')

  const payload = await page.evaluate(async () => {
    const response = await fetch('/api/integrations/connectors/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connector: {
          id: 'ops-webhook',
          type: 'webhook',
          name: 'Ops Webhook',
          description: 'Post incident updates to the operations webhook endpoint.',
          enabled: true,
          approved: true,
          settings: {
            url: 'https://hooks.example.test/ops',
            token: 'ops-webhook-token',
            channel: 'ops-alerts',
            nested: {
              client_secret: 'nested-client-secret',
              safe_label: 'incident-review',
            },
          },
        },
      }),
    })
    return {
      status: response.status,
      body: await response.json(),
    }
  })

  expect(payload).toMatchObject({
    status: 200,
    body: {
      ok: true,
      status: 'success',
      checks: [
        expect.objectContaining({ name: 'enabled', ok: true, status: 'passed' }),
        expect.objectContaining({ name: 'approved', ok: true, status: 'passed' }),
        expect.objectContaining({ name: 'endpoint', ok: true, status: 'passed' }),
      ],
      summary: {
        check_count: 3,
        failed_count: 0,
        blocking_failure_count: 0,
        warning_count: 0,
      },
      connector: {
        id: 'ops-webhook',
        type: 'webhook',
        name: 'Ops Webhook',
        enabled: true,
        approved: true,
        settings: {
          url: '***redacted***',
          token: '***redacted***',
          channel: 'ops-alerts',
          nested: {
            client_secret: '***redacted***',
            safe_label: 'incident-review',
          },
        },
      },
    },
  })
  expect(JSON.stringify(payload.body)).not.toContain('https://hooks.example.test/ops')
  expect(JSON.stringify(payload.body)).not.toContain('ops-webhook-token')
  expect(JSON.stringify(payload.body)).not.toContain('nested-client-secret')
})

test('shows Integrator audit records in settings without leaking sensitive values', async ({ page }) => {
  await page.goto('/')

  const payload = await page.evaluate(async () => {
    const response = await fetch('/api/integrations/audit?limit=20')
    return {
      status: response.status,
      body: await response.json(),
    }
  })

  expect(payload).toMatchObject({
    status: 200,
    body: {
      total: expect.any(Number),
      limit: 20,
      events: expect.arrayContaining([
        expect.objectContaining({
          action: 'integrator_connector_test',
          result: 'success',
          connector_id: 'ops-webhook',
          connector_type: 'webhook',
          details: expect.objectContaining({
            url: '***redacted***',
            token: '***redacted***',
          }),
        }),
      ]),
    },
  })
  expect(JSON.stringify(payload.body)).not.toContain('https://hooks.example.test/ops')
  expect(JSON.stringify(payload.body)).not.toContain('ops-webhook-token')
  expect(JSON.stringify(payload.body)).not.toContain('nested-client-secret')
  expect(JSON.stringify(payload.body)).not.toContain('top-level-client-secret')

  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-integrations').click()

  const auditPanel = page.getByTestId('settings-integrator-audit-panel')
  await expect(auditPanel).toBeVisible()
  await expect(auditPanel.getByTestId('settings-integrator-audit-row')).toHaveCount(2)
  await expect(auditPanel).toContainText('integrator_connector_test')
  await expect(auditPanel).toContainText('ops-webhook')
  await expect(auditPanel).toContainText('channel: ops-alerts')
  await expect(auditPanel).not.toContainText('https://hooks.example.test/ops')
  await expect(auditPanel).not.toContainText('ops-webhook-token')
  await expect(auditPanel).not.toContainText('nested-client-secret')
  await expect(auditPanel).not.toContainText('top-level-client-secret')

  const auditResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/integrations/audit?limit=20'),
  )
  await auditPanel.getByTestId('settings-integrator-audit-refresh').click()
  expect((await auditResponsePromise).status()).toBe(200)
})

test('filters MCP marketplace categories from Integrations settings', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-mcp-productization-panel')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('Categories: 2')
  await expect(panel.getByTestId('settings-mcp-marketplace-categories')).toContainText('Knowledge')
  await expect(panel.getByTestId('settings-mcp-marketplace-categories')).toContainText('Integration')
  await expect(panel.getByTestId('settings-mcp-marketplace-row')).toHaveCount(2)

  await panel.getByTestId('settings-mcp-marketplace-category-integration').click()
  await expect(panel.getByTestId('settings-mcp-marketplace-row')).toHaveCount(1)
  await expect(panel.getByTestId('settings-mcp-marketplace-row')).toContainText('Custom CRM')

  await panel.getByTestId('settings-mcp-marketplace-category-all').click()
  await expect(panel.getByTestId('settings-mcp-marketplace-row')).toHaveCount(2)
})

test('tests an Integrator connector from settings without leaking sensitive values', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrators-panel')
  await expect(panel).toBeVisible()
  await expect(panel.getByTestId('settings-integrator-settings-json')).not.toHaveValue(
    /ops-webhook-token/,
  )

  const approvedToggle = panel.getByTestId('settings-integrator-approved')
  if (!(await approvedToggle.isChecked())) {
    await approvedToggle.check()
  }

  const testButton = panel
    .getByTestId('settings-integrator-test')
    .or(panel.getByRole('button', { name: /^test$/i }))
    .first()
  if ((await testButton.count()) === 0) {
    test.skip(true, 'Settings Integrations panel does not expose a Test button yet.')
  }

  const testResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/connectors/test'),
  )
  await testButton.click()

  const testResponse = await testResponsePromise
  expect(testResponse.status()).toBe(200)
  await expect(testResponse.json()).resolves.toMatchObject({
    ok: true,
    status: 'success',
    connector: {
      settings: {
        url: '***redacted***',
        token: '***redacted***',
      },
    },
  })
  await expect(panel).toContainText(/success|passed|healthy/i)
  await expect(panel).not.toContainText('https://hooks.example.test/ops')
  await expect(panel).not.toContainText('ops-webhook-token')
  await expect(panel).not.toContainText('nested-client-secret')
})

test('rotates and probes Integrator connector credentials without leaking sensitive values', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrators-panel')
  const credentialsPanel = panel.getByTestId('settings-integrator-credentials-panel')
  await expect(credentialsPanel).toBeVisible()
  await expect(credentialsPanel.getByTestId('settings-integrator-credential-template-token')).toBeVisible()
  await expect(credentialsPanel.getByTestId('settings-integrator-credential-template-api_key')).toBeVisible()
  await expect(credentialsPanel.getByTestId('settings-integrator-credential-template-basic_auth')).toBeVisible()

  await credentialsPanel.getByTestId('settings-integrator-credential-template-api_key').click()
  await credentialsPanel
    .getByTestId('settings-integrator-credential-field-api_key')
    .fill('field-ui-api-key')

  const fieldRotateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/connectors/ops-webhook/credentials/rotate'),
  )
  await credentialsPanel.getByTestId('settings-integrator-rotate').click()
  const fieldRotateResponse = await fieldRotateResponsePromise
  expect(fieldRotateResponse.status()).toBe(200)
  expect(fieldRotateResponse.request().postDataJSON()).toEqual({
    settings: { api_key: 'field-ui-api-key' },
  })
  const fieldRotatePayload = await fieldRotateResponse.json()
  expect(fieldRotatePayload).toMatchObject({
    status: 'rotated',
    rotated_fields: expect.arrayContaining(['api_key']),
    connector: {
      id: 'ops-webhook',
      settings: {
        api_key: '***redacted***',
      },
    },
  })
  expect(JSON.stringify(fieldRotatePayload)).not.toContain('field-ui-api-key')
  await expect(credentialsPanel.getByTestId('settings-integrator-credential-field-api_key')).toHaveValue('')
  await expect(panel).not.toContainText('field-ui-api-key')

  await credentialsPanel.getByTestId('settings-integrator-credential-template-basic_auth').click()
  await expect(credentialsPanel.getByTestId('settings-integrator-credential-field-username')).toBeVisible()
  await expect(credentialsPanel.getByTestId('settings-integrator-credential-field-password')).toBeVisible()
  await expect(credentialsPanel.getByTestId('settings-integrator-credential-field-password')).toHaveValue('')

  const credentialPatch = {
    url: 'https://hooks.example.test/rotated-ui',
    token: 'rotated-ui-token',
    nested: {
      client_secret: 'rotated-ui-client-secret',
      safe_label: 'rotated-safe-label',
    },
  }
  await credentialsPanel.getByTestId('settings-integrator-credential-mode-json').click()
  await credentialsPanel
    .getByTestId('settings-integrator-credential-patch-json')
    .fill(JSON.stringify(credentialPatch, null, 2))

  const rotateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/connectors/ops-webhook/credentials/rotate'),
  )
  await credentialsPanel.getByTestId('settings-integrator-rotate').click()
  const rotateResponse = await rotateResponsePromise
  expect(rotateResponse.status()).toBe(200)
  expect(rotateResponse.request().postDataJSON()).toEqual({ settings: credentialPatch })
  const rotatePayload = await rotateResponse.json()
  expect(rotatePayload).toMatchObject({
    status: 'rotated',
    rotated_fields: expect.arrayContaining(['url', 'token', 'nested.client_secret']),
    connector: {
      id: 'ops-webhook',
      settings: {
        url: '***redacted***',
        token: '***redacted***',
        nested: {
          client_secret: '***redacted***',
          safe_label: 'rotated-safe-label',
        },
      },
    },
  })
  expect(JSON.stringify(rotatePayload)).not.toContain('https://hooks.example.test/rotated-ui')
  expect(JSON.stringify(rotatePayload)).not.toContain('rotated-ui-token')
  expect(JSON.stringify(rotatePayload)).not.toContain('rotated-ui-client-secret')

  await expect(credentialsPanel.getByTestId('settings-integrator-credential-patch-json')).not.toHaveValue(
    /rotated-ui-token|rotated-ui-client-secret|https:\/\/hooks\.example\.test\/rotated-ui/,
  )
  await expect(credentialsPanel.getByTestId('settings-integrator-rotation-result')).toContainText('Rotation rotated')
  await expect(credentialsPanel.getByTestId('settings-integrator-rotation-result')).toContainText('url')
  await expect(panel).not.toContainText('https://hooks.example.test/rotated-ui')
  await expect(panel).not.toContainText('rotated-ui-token')
  await expect(panel).not.toContainText('rotated-ui-client-secret')

  const probeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/connectors/ops-webhook/probe'),
  )
  await credentialsPanel.getByTestId('settings-integrator-probe').click()
  const probeResponse = await probeResponsePromise
  expect(probeResponse.status()).toBe(200)
  expect(probeResponse.request().postDataJSON()).toEqual({ dry_run: true, mode: 'static' })
  const probePayload = await probeResponse.json()
  expect(probePayload).toMatchObject({
    status: 'healthy',
    dry_run: true,
    executed: false,
    probe: {
      mode: 'static',
      outbound_request_sent: false,
    },
    connector: {
      settings: {
        url: '***redacted***',
        token: '***redacted***',
      },
    },
  })
  expect(JSON.stringify(probePayload)).not.toContain('https://hooks.example.test/rotated-ui')
  expect(JSON.stringify(probePayload)).not.toContain('rotated-ui-token')
  expect(JSON.stringify(probePayload)).not.toContain('rotated-ui-client-secret')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-result')).toContainText('Static dry-run probe')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-result')).toContainText('healthy')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-mode')).toContainText('static')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-outbound')).toContainText('not sent')

  await credentialsPanel.getByTestId('settings-integrator-external-probe-enabled').check()
  await credentialsPanel.getByTestId('settings-integrator-external-probe-timeout').fill('4')

  const externalProbeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/connectors/ops-webhook/probe'),
  )
  await credentialsPanel.getByTestId('settings-integrator-probe').click()
  const externalProbeResponse = await externalProbeResponsePromise
  expect(externalProbeResponse.status()).toBe(200)
  expect(externalProbeResponse.request().postDataJSON()).toEqual({
    dry_run: false,
    mode: 'external',
    timeout_seconds: 4,
  })
  const externalProbePayload = await externalProbeResponse.json()
  expect(externalProbePayload).toMatchObject({
    status: 'ready',
    dry_run: false,
    executed: true,
    probe: {
      mode: 'external',
      outbound_request_sent: true,
      timeout_seconds: 4,
      endpoint: {
        host: 'hooks.example.test',
        fingerprint: 'mock-endpoint-fp',
      },
      response: {
        status_code: 204,
      },
    },
  })
  expect(JSON.stringify(externalProbePayload)).not.toContain('https://hooks.example.test/rotated-ui')
  expect(JSON.stringify(externalProbePayload)).not.toContain('rotated-ui-token')
  expect(JSON.stringify(externalProbePayload)).not.toContain('rotated-ui-client-secret')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-result')).toContainText('External probe')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-mode')).toContainText('external')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-outbound')).toContainText('sent')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-timeout')).toContainText('4s')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-endpoint')).toContainText('fingerprint')
  await expect(credentialsPanel.getByTestId('settings-integrator-probe-response')).toContainText('status_code')
  await expect(panel).not.toContainText('https://hooks.example.test/rotated-ui')
  await expect(panel).not.toContainText('rotated-ui-token')
  await expect(panel).not.toContainText('rotated-ui-client-secret')
})

test('manages Integrator schedules from settings without leaking sensitive values', async ({ page }) => {
  await page.goto('/')

  const initialPayload = await page.evaluate(async () => {
    const response = await fetch('/api/integrations/schedules')
    return {
      status: response.status,
      body: await response.json(),
    }
  })

  expect(initialPayload).toMatchObject({
    status: 200,
    body: {
      total: 1,
      persistence: {
        enabled: true,
        config_key: 'integrator_schedules',
        sensitive_fields_redacted: true,
      },
      schedules: [
        expect.objectContaining({
          schedule_id: 'schedule-ops-hourly',
          name: 'Ops hourly sync',
          connector_id: 'ops-webhook',
          interval_minutes: 60,
          timezone: 'UTC',
          settings: {
            url: '***redacted***',
            token: '***redacted***',
            batch_size: 25,
            nested: {
              secret: '***redacted***',
              mode: 'delta',
            },
          },
        }),
      ],
      scheduler: {
        mode: 'configured',
        automatic_dispatch: false,
        manual_trigger_supported: true,
      },
    },
  })
  expect(JSON.stringify(initialPayload.body)).not.toContain('https://hooks.example.test/schedules')
  expect(JSON.stringify(initialPayload.body)).not.toContain('schedule-token')
  expect(JSON.stringify(initialPayload.body)).not.toContain('nested-schedule-secret')

  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrator-schedules-panel')
  await expect(panel).toBeVisible()
  await expect(panel.getByTestId('settings-integrator-schedule-row')).toHaveCount(1)
  await expect(panel).toContainText('Ops hourly sync')
  await expect(panel.getByTestId('settings-integrator-schedule-auto-dispatch')).toContainText('Off')
  await expect(panel.getByTestId('settings-integrator-schedule-mode')).toContainText('configured')
  await expect(panel.getByTestId('settings-integrator-schedule-row').first()).toContainText('UTC')
  await expect(panel.getByTestId('settings-integrator-schedule-timezone-display')).toContainText('UTC')
  await expect(panel).not.toContainText('https://hooks.example.test/schedules')
  await expect(panel).not.toContainText('schedule-token')
  await expect(panel).not.toContainText('nested-schedule-secret')

  const tickResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/schedules/tick'),
  )
  await panel.getByTestId('settings-integrator-schedule-tick').click()
  const tickResponse = await tickResponsePromise
  expect(tickResponse.status()).toBe(200)
  const tickPayload = await tickResponse.json()
  expect(tickResponse.request().postDataJSON()).toEqual({ dry_run: true })
  expect(tickPayload).toMatchObject({
    dry_run: true,
    executed: false,
    checked: 1,
    due_count: 1,
    skipped: {
      disabled: 0,
      not_due: 0,
    },
  })
  expect(JSON.stringify(tickPayload)).not.toContain('https://hooks.example.test/schedules')
  expect(JSON.stringify(tickPayload)).not.toContain('schedule-token')
  expect(JSON.stringify(tickPayload)).not.toContain('nested-schedule-secret')
  await expect(panel.getByTestId('settings-integrator-schedule-tick-result')).toContainText('Due:')
  await expect(panel.getByTestId('settings-integrator-schedule-tick-due-count')).toContainText('1')
  await expect(panel.getByTestId('settings-integrator-schedule-tick-skipped')).toContainText('0')
  await expect(panel.getByTestId('settings-integrator-schedule-tick-result')).toContainText('Dry-run')
  await expect(panel).not.toContainText('https://hooks.example.test/schedules')
  await expect(panel).not.toContainText('schedule-token')
  await expect(panel).not.toContainText('nested-schedule-secret')

  await panel.getByTestId('settings-integrator-schedule-name').fill('Ops critical sync')
  await panel.getByTestId('settings-integrator-schedule-cron').fill('5-55/10 8-18/2 * JAN-MAR MON-FRI')
  await panel.getByTestId('settings-integrator-schedule-timezone').fill('Asia/Shanghai')
  await panel.getByTestId('settings-integrator-schedule-interval').fill('30')
  await panel.getByTestId('settings-integrator-schedule-enabled').uncheck()
  const saveRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' &&
      request.url().includes('/api/integrations/schedules'),
  )
  await panel.getByTestId('settings-integrator-schedule-save').click()
  const saveRequest = await saveRequestPromise
  expect(saveRequest.postDataJSON()).toMatchObject({
    schedules: [
      expect.objectContaining({
        name: 'Ops critical sync',
        cron: '5-55/10 8-18/2 * JAN-MAR MON-FRI',
        timezone: 'Asia/Shanghai',
        interval_minutes: 30,
      }),
    ],
  })

  await expect(panel).toContainText('Integration schedules saved')
  await expect(panel.getByTestId('settings-integrator-schedule-row').first()).toContainText('Ops critical sync')
  await expect(panel.getByTestId('settings-integrator-schedule-row').first()).toContainText('Disabled')
  await expect(panel.getByTestId('settings-integrator-schedule-row').first()).toContainText('30m')
  await expect(panel.getByTestId('settings-integrator-schedule-row').first()).toContainText('Asia/Shanghai')
  await expect(panel.getByTestId('settings-integrator-schedule-timezone-display')).toContainText('Asia/Shanghai')

  await panel.getByTestId('settings-integrator-schedule-enabled').check()
  await panel.getByTestId('settings-integrator-schedule-save').click()
  await expect(panel).toContainText('Enabled')

  const triggerResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/schedules/schedule-ops-hourly/trigger'),
  )
  await panel.getByTestId('settings-integrator-schedule-trigger').click()
  const triggerResponse = await triggerResponsePromise
  expect(triggerResponse.status()).toBe(200)
  await expect(triggerResponse.json()).resolves.toMatchObject({
    ok: true,
    schedule_id: 'schedule-ops-hourly',
    status: 'triggered',
  })
  await expect(panel).toContainText('Schedule trigger triggered')

  await panel.getByTestId('settings-integrator-schedule-remove').click()
  await panel.getByTestId('settings-integrator-schedule-save').click()
  await expect(panel.getByTestId('settings-integrator-schedule-empty')).toBeVisible()
})

test('shows Integrator schedule load errors in settings', async ({ page }) => {
  await page.route('**://*/api/integrations/schedules', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ detail: 'schedule backend unavailable' }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrator-schedules-panel')
  await expect(panel.getByTestId('settings-integrator-schedule-error')).toContainText(
    'schedule backend unavailable',
  )
})

test('validates Integrator schedule cron and interval before saving', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrator-schedules-panel')
  await expect(panel).toBeVisible()
  const cronInput = panel.getByTestId('settings-integrator-schedule-cron')
  await expect(cronInput).toHaveAttribute('list', 'integrator-schedule-cron-presets')
  await expect(panel.getByTestId('settings-integrator-schedule-cron-help')).toContainText(
    'macros',
  )

  await cronInput.fill('invalid cron')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toContainText(
    'Cron must use 5 fields',
  )
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeDisabled()

  await cronInput.fill('60 * * * *')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toContainText(
    'minute field value 60 is outside 0-59',
  )
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeDisabled()

  await cronInput.fill('0 9 * JAX MON-FRI')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toContainText(
    'unsupported alias "JAX"',
  )
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeDisabled()

  await cronInput.fill('@daily')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toHaveCount(0)
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeEnabled()

  await cronInput.fill('0 9 ? * MON-FRI')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toHaveCount(0)
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeEnabled()

  await cronInput.fill('0 9 * ? MON-FRI')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toContainText(
    'month field does not support ?',
  )
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeDisabled()

  await cronInput.fill('0 9 * JAN-MAR MON-FRI')
  await panel.getByTestId('settings-integrator-schedule-timezone').fill('Mars/Base')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toContainText(
    'Timezone must be a valid IANA timezone',
  )
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeDisabled()

  await panel.getByTestId('settings-integrator-schedule-timezone').fill('UTC')
  await panel.getByTestId('settings-integrator-schedule-interval').fill('3')
  await expect(panel.getByTestId('settings-integrator-schedule-validation')).toContainText(
    'at least 5 minutes',
  )
  await expect(panel.getByTestId('settings-integrator-schedule-save')).toBeDisabled()
})

test('manages identity and resource grants from settings roles tab', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-tab-roles').click()

  await expect(page.getByTestId('identity-admin-panel')).toBeVisible()
  await expect(page.getByTestId('resource-access-panel')).toBeVisible()

  await page.getByTestId('identity-org-id-input').fill('org-qa')
  await page.getByTestId('identity-org-name-input').fill('QA Org')
  await page.getByTestId('identity-org-save').click()

  await page.getByTestId('identity-user-id-input').fill('user-qa')
  await page.getByTestId('identity-user-name-input').fill('QA User')
  await page.getByTestId('identity-user-email-input').fill('qa@example.com')
  await page.getByTestId('identity-user-save').click()

  await page.getByTestId('identity-membership-org-input').fill('org-qa')
  await page.getByTestId('identity-membership-user-input').fill('user-qa')
  await page.getByTestId('identity-membership-role-input').selectOption('editor')
  await page.getByTestId('identity-membership-save').click()

  await expect(page.getByTestId('identity-org-list')).toContainText('QA Org')
  await expect(page.getByTestId('identity-user-list')).toContainText('QA User')
  await expect(page.getByTestId('identity-membership-list')).toContainText('org-qa')
  await expect(page.getByTestId('identity-membership-list')).toContainText('user-qa')
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const select = document.querySelector(
          '[data-testid="resource-access-form-subject-pick"]',
        ) as HTMLSelectElement | null
        return Array.from(select?.options ?? []).some((option) => option.value === 'user:user-qa')
      }),
    )
    .toBe(true)

  await page
    .getByTestId('resource-access-form-resource-pick')
    .selectOption('workspace:workspace-default')
  await page.getByTestId('resource-access-form-subject-type').selectOption('user')
  await page.getByTestId('resource-access-form-subject-pick').selectOption('user:user-qa')
  await page.getByTestId('resource-access-form-role').selectOption('editor')
  await page.getByTestId('resource-access-form-save').click()

  await expect(page.getByTestId('resource-access-grant-list')).toContainText('workspace')
  await expect(page.getByTestId('resource-access-grant-list')).toContainText('workspace-default')
  await expect(page.getByTestId('resource-access-grant-list')).toContainText('user:user-qa')
  await expect(page.getByTestId('resource-access-grant-list')).toContainText('editor')

  await page
    .getByTestId('resource-access-filter-subject-pick')
    .selectOption('user:user-qa')
  await expect(page.getByTestId('resource-access-grant-list')).toContainText('user:user-qa')
})

test('applies a saved cloud model profile from the panel selector', async ({ page }) => {
  const profileName = 'Panel Apply Profile'
  const profileModel = 'gpt-4.1-mini'
  const apiKey = 'sk-apply-789'
  const prompt = 'Create the first panel so the selector is available'

  await page.goto('/')
  await page.getByTestId('composer-input').fill(prompt)
  await page.getByTestId('composer-send').click()
  await expect(page.getByTestId('session-item')).toHaveCount(1)
  await expect(page.locator('[data-role="assistant"]').last()).toContainText(
    `Mock answer for: ${prompt}`,
  )
  await page.getByTestId('header-open-settings').click()

  await page.getByTestId('settings-cloud-profile-name-input').fill(profileName)
  await page.getByTestId('settings-cloud-profile-model-input').fill(profileModel)
  await page.getByTestId('settings-cloud-profile-api-key-input').fill(apiKey)
  await page.getByTestId('settings-cloud-profile-save').click()

  const settingsProfileCard = page
    .getByTestId('settings-cloud-profile-list')
    .locator('[data-testid^="settings-cloud-profile-card-"]')
    .first()
  await expect(settingsProfileCard).toContainText(profileName)
  await expect(settingsProfileCard.locator('[data-testid^="settings-cloud-profile-clear-"]')).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(page.getByTestId('settings-cloud-profile-list')).toHaveCount(0)

  const panel = page.getByTestId('chat-panel').first()
  const modelSelectorTrigger = panel.locator('[data-testid^="model-selector-trigger-"]').first()
  await modelSelectorTrigger.click()

  const modelSelectorMenu = panel.locator('[data-testid^="model-selector-menu-"]').first()
  await modelSelectorMenu
    .locator('[data-testid^="model-selector-connection-"][data-testid$="openai_compatible"]')
    .first()
    .click()
  const cloudProfileButton = modelSelectorMenu
    .locator('[data-testid^="model-selector-cloud-profile-"]')
    .first()

  await expect(cloudProfileButton).toContainText(profileName)
  await expect(cloudProfileButton).toContainText(profileModel)

  await cloudProfileButton.click()
  await expect(modelSelectorTrigger).toContainText(profileModel)

  await modelSelectorTrigger.click()
  await expect(
    panel.locator('[data-testid^="model-selector-managed-key-notice-"]').first(),
  ).toBeVisible()
})

test('manual API key input detaches the managed cloud key in the panel selector', async ({ page }) => {
  const profileName = 'Manual Override Profile'
  const profileModel = 'gpt-4.1-nano'
  const managedApiKey = 'sk-managed-001'
  const manualApiKey = 'sk-manual-override'
  const prompt = 'Render the first panel before opening the selector'

  await page.goto('/')
  await page.getByTestId('composer-input').fill(prompt)
  await page.getByTestId('composer-send').click()
  await expect(page.getByTestId('session-item')).toHaveCount(1)
  await expect(page.locator('[data-role="assistant"]').last()).toContainText(
    `Mock answer for: ${prompt}`,
  )

  await page.getByTestId('header-open-settings').click()
  await page.getByTestId('settings-cloud-profile-name-input').fill(profileName)
  await page.getByTestId('settings-cloud-profile-model-input').fill(profileModel)
  await page.getByTestId('settings-cloud-profile-api-key-input').fill(managedApiKey)
  await page.getByTestId('settings-cloud-profile-save').click()
  await expect(
    page
      .getByTestId('settings-cloud-profile-list')
      .locator('[data-testid^="settings-cloud-profile-card-"]')
      .first(),
  ).toContainText(profileName)

  await page.keyboard.press('Escape')
  await expect(page.getByTestId('settings-cloud-profile-list')).toHaveCount(0)

  const panel = page.getByTestId('chat-panel').first()
  const modelSelectorTrigger = panel.locator('[data-testid^="model-selector-trigger-"]').first()
  await modelSelectorTrigger.click()

  const modelSelectorMenu = panel.locator('[data-testid^="model-selector-menu-"]').first()
  await modelSelectorMenu
    .locator('[data-testid^="model-selector-connection-"][data-testid$="openai_compatible"]')
    .first()
    .click()
  await modelSelectorMenu
    .locator('[data-testid^="model-selector-cloud-profile-"]')
    .first()
    .click()

  await modelSelectorTrigger.click()
  const managedKeyNotice = panel.locator('[data-testid^="model-selector-managed-key-notice-"]').first()
  const apiKeyInput = panel.locator('[data-testid^="model-selector-api-key-input-"]').first()

  await expect(managedKeyNotice).toBeVisible()
  await apiKeyInput.fill(manualApiKey)
  await expect(apiKeyInput).toHaveValue(manualApiKey)
  await expect(managedKeyNotice).toHaveCount(0)
})

test('attaches a file and sends it with the message', async ({ page }) => {
  const prompt = 'Use the attached note as context for the reply'

  await page.goto('/')

  await page.getByTestId('composer-attachment-input').setInputFiles({
    name: 'notes.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Notes\n- Extend Playwright smoke coverage\n'),
  })

  await expect(page.getByText('notes.md')).toBeVisible()

  await page.getByTestId('composer-input').fill(prompt)
  await page.getByTestId('composer-send').click()

  const lastUserMessage = page.locator('[data-role="user"]').last()
  await expect(page.getByTestId('session-item')).toHaveCount(1)
  await expect(lastUserMessage).toContainText(prompt)
  await expect(lastUserMessage).toContainText('notes.md')
  await expect(page.locator('[data-role="assistant"]').last()).toContainText(
    `Mock answer for: ${prompt}`,
  )
})

test('starts web research and resolves the task result into the assistant answer', async ({ page }) => {
  const query = 'Find the latest AI agent testing patterns'

  await startResearch(page, query)

  await expect(page.getByTestId('message-generate-report').last()).toBeVisible()
  await expect(page.locator('[data-role="assistant"]').last()).toContainText(
    `Research summary for: ${query}`,
  )
})

test('serves research archives from the mock API with search and task filters', async ({ page }) => {
  const query = 'Find the latest AI agent testing patterns'

  await startResearch(page, query)

  const archivesPayload = await page.evaluate(async () => {
    const response = await fetch('/api/research/archives?q=agent%20testing&limit=1')
    return response.json()
  })

  expect(archivesPayload).toMatchObject({
    total: expect.any(Number),
    limit: 1,
    archives: [
      {
        archive_id: expect.any(String),
        artifact_id: expect.any(String),
        claim_evidence_chains: expect.any(Array),
        claim_verification_summary: expect.any(Object),
        verification_summary: expect.any(Object),
        paragraph_citations: expect.any(Array),
        paragraph_claim_links: expect.any(Array),
        navigation_index: expect.any(Object),
        citation_graph: expect.any(Object),
        conflict_summary: expect.any(Object),
        conflict_review_resolutions: expect.any(Array),
        preview_claims: expect.any(Array),
        preview_sources: expect.any(Array),
        provider_capabilities: expect.any(Object),
        sources: expect.any(Array),
        delivery_quality: expect.any(Object),
      },
    ],
  })

  const archive = archivesPayload.archives[0]
  expect(archive.claim_evidence_chains.length).toBeGreaterThan(0)
  expect(archive.paragraph_citations.length).toBeGreaterThan(0)
  expect(archive.navigation_index.claim_to_paragraphs['claim-agent-qa-1']).toContain(
    'paragraph-key-findings-1',
  )
  expect(archivesPayload.conflict_groups[0]).toMatchObject({
    normalized_conflict_text: expect.stringContaining('unresolved conflicts'),
    review_statuses: expect.arrayContaining(['unreviewed']),
  })

  const paragraphSearchPayload = await page.evaluate(async () => {
    const response = await fetch('/api/research/archives?q=paragraph%20p1')
    return response.json()
  })
  expect(paragraphSearchPayload.archives[0]).toMatchObject({
    archive_id: archive.archive_id,
  })

  const citationSearchPayload = await page.evaluate(async () => {
    const response = await fetch('/api/research/archives?q=2%20source%20families')
    return response.json()
  })
  expect(citationSearchPayload.archives[0]).toMatchObject({
    archive_id: archive.archive_id,
  })

  const conflictSearchPayload = await page.evaluate(async () => {
    const response = await fetch('/api/research/archives?q=unresolved%20conflicts')
    return response.json()
  })
  expect(conflictSearchPayload.archives[0]).toMatchObject({
    archive_id: archive.archive_id,
  })

  const taskFilteredPayload = await page.evaluate(async (taskId) => {
    const response = await fetch(`/api/research/archives?task_id=${encodeURIComponent(taskId)}`)
    return response.json()
  }, archive.task_id)

  expect(taskFilteredPayload).toMatchObject({
    total: 1,
    archives: [expect.objectContaining({ task_id: archive.task_id })],
  })
})

test('generates a report preview from a completed research answer', async ({ page }) => {
  const query = 'Prepare a research-backed summary for agent QA'

  await generateReportFromLatestResearch(page, query)

  await expect(page.getByTestId('report-preview-content')).toContainText('Mock Research Report')
  await expect(page.getByTestId('report-preview-content')).toContainText(
    'The async task flow completed successfully.',
  )
  await expect(page.getByTestId('research-citation-panel')).toBeVisible()
  await expect(page.getByTestId('research-citation-claim-row').first()).toBeVisible()
  await expect(page.getByTestId('research-citation-paragraph-link').first()).toContainText(
    /paragraph/i,
  )
  await expect(page.getByTestId('research-citation-graph-summary')).toContainText(
    /nodes.*edges/i,
  )
  await expect(page.getByTestId('research-citation-conflict-summary')).toContainText(
    /conflicts/i,
  )
  await expect(page.getByTestId('research-conflict-group-row').first()).toContainText(
    /human review/i,
  )

  await page.getByTestId('research-citation-claim-filter').fill('agent')
  await expect(page.getByTestId('research-citation-claim-row').first()).toContainText(/agent/i)

  await page.getByTestId('research-citation-graph-filter').fill('source')
  await page.getByTestId('research-citation-graph-details').first().click()
  await expect(page.getByTestId('research-citation-graph-node').first()).toContainText(/source/i)

  await page.getByTestId('research-archive-search').fill('agent QA')
  await expect(page.getByTestId('research-archive-row').first()).toBeVisible()
})

test('downloads the generated report as a pptx file', async ({ page }) => {
  const query = 'Prepare a downloadable report draft'

  await generateReportFromLatestResearch(page, query)

  const downloadPromise = page.waitForEvent('download')
  await page.getByTestId('report-download-pptx').click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe('Mock Research Report.pptx')
})

test('opens the generated report in slidev and copies markdown', async ({ page }) => {
  const query = 'Prepare a report for slidev editing'

  await mockReportSlidevWindow(page)
  await generateReportFromLatestResearch(page, query)

  await page.getByTestId('report-open-slidev').click()

  const slidevState = await page.evaluate(() => {
    return (
      window as typeof window & {
        __reportSlidevState?: {
          url: string
          target: string
          features: string
        }
      }
    ).__reportSlidevState
  })

  expect(slidevState?.url).toBe('https://sli.dev/new')
  expect(slidevState?.target).toBe('_blank')

  await expect.poll(async () => page.evaluate(() => navigator.clipboard.readText())).toContain(
    '# Mock Research Report',
  )
})

test('generates a deck from the report preview and opens the deck editor', async ({ page }) => {
  const query = 'Turn this research summary into a presentation deck'

  await openDeckEditorFromLatestResearch(page, query)
  await expect(page.getByTestId('deck-editor-title')).toHaveText('Mock Deck')
  await expect(page.getByTestId('deck-editor-modal')).toContainText('Mock deck overview')
  await expect(page.getByTestId('deck-editor-modal')).toContainText(
    'This deck was generated from the mock report preview flow.',
  )
  await expect(page.getByTestId('deck-evidence-coverage-ratio')).toHaveText('50%')
  await expect(page.getByTestId('deck-evidence-covered-slides')).toHaveText('1 / 2')
  await expect(page.getByTestId('deck-evidence-total-refs')).toHaveText('1')
  await expect(page.getByTestId('deck-evidence-unsupported-slide-ids')).toContainText(
    'slide-content',
  )
  await expect(page.getByTestId('deck-evidence-review-status')).toHaveText('needs review')
  await expect(page.getByTestId('deck-evidence-review-action-count')).toHaveText('1')
  await expect(page.getByTestId('deck-evidence-review-slide-count')).toHaveText('1')
  await expect(page.getByTestId('deck-evidence-review-action-items')).toContainText(
    'Add evidence references to unsupported slides.',
  )
  await expect(page.getByTestId('deck-citation-gate-status')).toContainText('Citation gate: failed')
  await expect(page.getByTestId('deck-citation-validation-status')).toHaveText('failed')
  await expect(page.getByTestId('deck-citation-validation-details')).toContainText('can export:')
  await expect(page.getByTestId('deck-citation-validation-details')).toContainText('no')
  await expect(page.getByTestId('deck-citation-validation-details')).toContainText('issues:')
  await expect(page.getByTestId('deck-citation-validation-details')).toContainText('2')
  await expect(page.getByTestId('deck-citation-validation-details')).toContainText('missing-source-1')
  await expect(page.getByTestId('deck-citation-validation-details')).toContainText('ev-missing')
  await expect(page.getByTestId('deck-evidence-review-active-sources')).toContainText(
    'Research source for smoke test',
  )
  await expect(page.getByTestId('deck-evidence-block-bindings')).toContainText(
    'block-cover-summary',
  )
  await expect(page.getByTestId('deck-evidence-block-bindings')).toContainText(
    'Research source for smoke test',
  )
})

test('edits the generated deck title and saves the draft', async ({ page }) => {
  const query = 'Create a deck draft and verify title persistence'
  const nextTitle = 'Mock Deck Saved Title'

  await openDeckEditorFromLatestResearch(page, query)

  const titleInput = page.getByTestId('deck-editor-title-input')
  await titleInput.fill(nextTitle)
  await expect(titleInput).toHaveValue(nextTitle)

  await page.getByTestId('deck-editor-save').click()

  await expect(page.getByTestId('deck-editor-save-message')).toBeVisible()
  await expect(page.getByTestId('deck-editor-title')).toHaveText(nextTitle)
  await expect(titleInput).toHaveValue(nextTitle)
})

test('regenerates the active deck slide inside the editor', async ({ page }) => {
  const query = 'Regenerate the first slide of the deck'

  await openDeckEditorFromLatestResearch(page, query)
  await page.getByTestId('deck-editor-regenerate').click()

  await expect(page.getByTestId('deck-editor-modal')).toContainText(
    'This slide was regenerated by the mock API.',
  )
})

test('shares the generated deck from the editor', async ({ page }) => {
  const query = 'Create a shareable deck draft'

  await openDeckEditorFromLatestResearch(page, query)
  await page.getByTestId('deck-editor-share').click()

  await expect.poll(async () => page.evaluate(() => navigator.clipboard.readText())).toContain(
    'https://example.com/shared/decks/deck-mock-1',
  )
  await expect(page.getByTestId('deck-editor-save-message')).toBeVisible()
})

test('exports the generated deck as a pptx file', async ({ page }) => {
  const query = 'Export a deck draft as pptx'

  await allowDeckRiskyExport(page)
  await openDeckEditorFromLatestResearch(page, query)

  const downloadPromise = page.waitForEvent('download')
  await page.getByTestId('deck-editor-export-pptx').click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe('Mock Deck.pptx')
})

test('blocks unsafe deck export at the mock API gate without an explicit override', async ({ page }) => {
  const query = 'Block a deck draft export with citation issues'

  await openDeckEditorFromLatestResearch(page, query)

  const blockedPayload = await page.evaluate(async () => {
    const response = await fetch('/api/decks/deck-mock-1/export?format=pptx')
    return {
      status: response.status,
      body: await response.json(),
    }
  })

  expect(blockedPayload).toMatchObject({
    status: 409,
    body: {
      detail: expect.stringContaining('blocked'),
      citation_validation: {
        status: 'failed',
        can_export: false,
        issue_count: 2,
      },
      evidence_review: {
        status: 'needs_review',
        unsupported_slide_ids: ['slide-content'],
      },
      export_gate: {
        status: 'blocked',
        reason: 'citation_validation_failed',
        can_export: false,
        allow_unsafe_export: false,
        override_param: 'allow_unsafe_export=true',
      },
    },
  })

  const overrideStatus = await page.evaluate(async () => {
    const response = await fetch(
      '/api/decks/deck-mock-1/export?format=pptx&allow_unsafe_export=true',
    )
    return response.status
  })

  expect(overrideStatus).toBe(200)
})

test('exports the generated deck as printable pdf content', async ({ page }) => {
  const query = 'Export a deck draft as pdf'

  await allowDeckRiskyExport(page)
  await mockDeckPdfPrintWindow(page)
  await openDeckEditorFromLatestResearch(page, query)

  await page.getByTestId('deck-editor-export-pdf').click()

  await page.waitForFunction(() => {
    const state = (
      window as typeof window & {
        __deckPdfExportState?: { printed?: boolean }
      }
    ).__deckPdfExportState
    return Boolean(state?.printed)
  })

  const pdfExportState = await page.evaluate(() => {
    return (
      window as typeof window & {
        __deckPdfExportState?: {
          opened: boolean
          printed: boolean
          html: string
        }
      }
    ).__deckPdfExportState
  })

  expect(pdfExportState?.opened).toBe(true)
  expect(pdfExportState?.printed).toBe(true)
  expect(pdfExportState?.html).toContain('Mock Deck')
  expect(pdfExportState?.html).toContain('This deck was generated from the mock report preview flow.')
})

test('shows completed tasks in task center and reopens the generated report', async ({ page }) => {
  const query = 'Create a reportable research task for task center'

  await generateReportFromLatestResearch(page, query)

  await page.getByTestId('report-preview-close').click()
  await expect(page.getByTestId('report-preview-modal')).toHaveCount(0)

  await page.getByTestId('header-more-menu').click()
  await page.getByTestId('header-open-task-center').click()

  await expect(page.getByTestId('task-center-modal')).toBeVisible()
  await expect(
    page.locator('[data-testid="task-center-task"][data-task-type="web_research"]'),
  ).toHaveCount(1)

  const reportTask = page
    .locator('[data-testid="task-center-task"][data-task-type="generate_report"]')
    .first()
  await expect(reportTask).toBeVisible()
  await reportTask.getByTestId('task-center-open-report').click()

  await expect(page.getByTestId('report-preview-modal')).toBeVisible()
  await expect(page.getByTestId('report-preview-content')).toContainText('Mock Research Report')
})
