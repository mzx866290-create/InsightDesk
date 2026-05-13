import { expect, test, openAdvancedSettings } from './support/testHarness'

import type { Locator } from '@playwright/test'

const OPS_WEBHOOK_CONNECTOR_ID = 'ops-webhook'

async function selectIntegratorConnector(panel: Locator, connectorId: string): Promise<Locator> {
  const connectorRow = panel.locator(
    `[data-testid="settings-integrator-connector-row"][data-connector-id="${connectorId}"]`,
  )
  await expect(connectorRow).toHaveCount(1)
  await connectorRow.click()

  const connectorDetails = panel.locator(
    `[data-testid="settings-integrator-connector-details"][data-connector-id="${connectorId}"]`,
  )
  await expect(connectorDetails).toBeVisible()
  return connectorDetails
}

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
  await openAdvancedSettings(page)
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
  await openAdvancedSettings(page)
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

test('hot updates MCP config and sends the expected body', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-mcp-productization-panel')
  await expect(panel).toBeVisible()

  const hotUpdateRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' &&
      request.url().includes('/api/connectors/mcp/config'),
  )
  await panel.getByTestId('settings-mcp-hot-update').click()

  const hotUpdateRequest = await hotUpdateRequestPromise
  const hotUpdateBody = hotUpdateRequest.postDataJSON()
  expect(hotUpdateBody).toMatchObject({
    servers: {},
  })
  await expect(panel.getByTestId('settings-mcp-notice')).toContainText('hot update applied')
  await expect(panel.getByTestId('settings-mcp-runtime-status')).toContainText('ok')
  await expect(panel.getByTestId('settings-mcp-runtime-summary')).toContainText('Alerts: 0')
})

test('shows MCP hot update errors in settings', async ({ page }) => {
  await page.route('**://*/api/connectors/mcp/config', async (route) => {
    if (route.request().method() === 'PUT') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ detail: 'mcp hot update failed' }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-mcp-productization-panel')
  await expect(panel).toBeVisible()
  await panel.getByTestId('settings-mcp-hot-update').click()

  await expect(panel.getByTestId('settings-mcp-error')).toContainText('mcp hot update failed')
})

test('shows unhealthy MCP runtime summary and alert details', async ({ page }) => {
  await page.route('**://*/api/connectors/mcp/runtime-health', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          status: 'degraded',
          servers: [
            {
              name: 'knowledge-base',
              status: 'healthy',
              healthy: true,
              tool_count: 2,
              tools: ['knowledge_lookup', 'knowledge_diagnostics'],
              duration_ms: 24.5,
              error: null,
            },
            {
              name: 'custom-crm',
              status: 'error',
              healthy: false,
              tool_count: 0,
              tools: [],
              duration_ms: 250.4,
              error: 'Mock CRM handshake failed',
            },
          ],
          summary: {
            total: 2,
            healthy: 1,
            unhealthy: 1,
            tool_count: 2,
            status_counts: { healthy: 1, error: 1 },
            alert_count: 1,
            unhealthy_connectors: ['custom-crm'],
            slow_connectors: [],
          },
          history: [],
          history_limit: 20,
        }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-mcp-productization-panel')
  await expect(panel).toBeVisible()

  await expect(panel.getByTestId('settings-mcp-runtime-status')).toContainText('degraded')
  await expect(panel.getByTestId('settings-mcp-runtime-summary')).toContainText('Healthy: 1')
  await expect(panel.getByTestId('settings-mcp-runtime-summary')).toContainText('Unhealthy: 1')
  await expect(panel.getByTestId('settings-mcp-runtime-summary')).toContainText('Alerts: 1')
  await expect(panel.getByTestId('settings-mcp-runtime-alert')).toContainText('Runtime alerts: 1')
  await expect(panel.getByTestId('settings-mcp-runtime-alert')).toContainText('custom-crm')
})

test('tests an Integrator connector from settings without leaking sensitive values', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrators-panel')
  await expect(panel).toBeVisible()
  const connectorDetails = await selectIntegratorConnector(panel, OPS_WEBHOOK_CONNECTOR_ID)
  await expect(connectorDetails.getByTestId('settings-integrator-settings-json')).not.toHaveValue(
    /ops-webhook-token/,
  )

  const approvedToggle = connectorDetails.getByTestId('settings-integrator-approved')
  if (!(await approvedToggle.isChecked())) {
    await approvedToggle.check()
  }

  const testButton = panel.locator(
    `[data-testid="settings-integrator-test"][data-connector-id="${OPS_WEBHOOK_CONNECTOR_ID}"]`,
  )
  await expect(testButton).toBeVisible()

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

test('rejects non-object Integrator connector settings JSON before save or test', async ({ page }) => {
  const connectorRequests: string[] = []
  page.on('request', (request) => {
    const url = request.url()
    if (
      (request.method() === 'PUT' && url.includes('/api/integrations/connectors')) ||
      (request.method() === 'POST' && url.includes('/api/integrations/connectors/test'))
    ) {
      connectorRequests.push(`${request.method()} ${url}`)
    }
  })

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrators-panel')
  const connectorDetails = await selectIntegratorConnector(panel, OPS_WEBHOOK_CONNECTOR_ID)
  const settingsJson = connectorDetails.getByTestId('settings-integrator-settings-json')
  const saveButton = panel.getByTestId('settings-integrators-save')
  const testButton = panel.locator(
    `[data-testid="settings-integrator-test"][data-connector-id="${OPS_WEBHOOK_CONNECTOR_ID}"]`,
  )

  const approvedToggle = connectorDetails.getByTestId('settings-integrator-approved')
  if (!(await approvedToggle.isChecked())) {
    await approvedToggle.check()
  }

  await settingsJson.fill('{')
  await saveButton.click()
  await expect(panel.getByTestId('settings-integrator-error')).toContainText('Connector settings JSON is invalid')
  await page.waitForTimeout(250)
  expect(connectorRequests).toEqual([])

  await testButton.click()
  await expect(panel.getByTestId('settings-integrator-error')).toContainText('Connector settings JSON is invalid')
  await page.waitForTimeout(250)
  expect(connectorRequests).toEqual([])

  await settingsJson.fill('[]')
  await saveButton.click()
  await expect(panel.getByTestId('settings-integrator-error')).toContainText('must be a JSON object')
  await page.waitForTimeout(250)
  expect(connectorRequests).toEqual([])

  await testButton.click()
  await expect(panel.getByTestId('settings-integrator-error')).toContainText('must be a JSON object')
  await page.waitForTimeout(250)
  expect(connectorRequests).toEqual([])

  await settingsJson.fill(JSON.stringify({ url: '***redacted***', token: '***redacted***', channel: 'ops-alerts' }, null, 2))

  const testResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/integrations/connectors/test'),
  )
  await testButton.click()
  expect((await testResponsePromise).status()).toBe(200)

  const saveRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' &&
      request.url().includes('/api/integrations/connectors'),
  )
  await saveButton.click()
  expect((await saveRequestPromise).postDataJSON()).toMatchObject({
    connectors: expect.arrayContaining([
      expect.objectContaining({
        id: OPS_WEBHOOK_CONNECTOR_ID,
        settings: expect.objectContaining({
          channel: 'ops-alerts',
        }),
      }),
    ]),
  })
  expect(connectorRequests.some((request) => request.startsWith('POST '))).toBe(true)
  expect(connectorRequests.some((request) => request.startsWith('PUT '))).toBe(true)
})

test('rotates and probes Integrator connector credentials without leaking sensitive values', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrators-panel')
  const connectorDetails = await selectIntegratorConnector(panel, OPS_WEBHOOK_CONNECTOR_ID)
  const credentialsPanel = connectorDetails.getByTestId('settings-integrator-credentials-panel')
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
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrator-schedules-panel')
  const scheduleRow = panel.locator(
    '[data-testid="settings-integrator-schedule-row"][data-schedule-id="schedule-ops-hourly"]',
  )
  await expect(panel).toBeVisible()
  await expect(panel.getByTestId('settings-integrator-schedule-row')).toHaveCount(1)
  await expect(scheduleRow).toHaveCount(1)
  await expect(panel).toContainText('Ops hourly sync')
  await expect(panel.getByTestId('settings-integrator-schedule-auto-dispatch')).toContainText('Off')
  await expect(panel.getByTestId('settings-integrator-schedule-mode')).toContainText('configured')
  await expect(scheduleRow.getByTestId('settings-integrator-schedule-row-timezone')).toContainText('UTC')
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
  await expect(scheduleRow.getByTestId('settings-integrator-schedule-row-name')).toContainText('Ops critical sync')
  await expect(scheduleRow.getByTestId('settings-integrator-schedule-row-status')).toContainText('Disabled')
  await expect(scheduleRow.getByTestId('settings-integrator-schedule-row-interval')).toContainText('30m')
  await expect(scheduleRow.getByTestId('settings-integrator-schedule-row-timezone')).toContainText('Asia/Shanghai')
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
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-integrations').click()

  const panel = page.getByTestId('settings-integrator-schedules-panel')
  await expect(panel.getByTestId('settings-integrator-schedule-error')).toContainText(
    'schedule backend unavailable',
  )
})

test('validates Integrator schedule cron and interval before saving', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
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
