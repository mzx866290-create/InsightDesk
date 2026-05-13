import { expect, test } from './support/testHarness'
import { Buffer } from 'node:buffer'

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
  await expect(page.getByTestId('composer-research')).toContainText('分析')
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
