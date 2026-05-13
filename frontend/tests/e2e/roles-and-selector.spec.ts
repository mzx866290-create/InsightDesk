import { expect, test, openAdvancedSettings } from './support/testHarness'

test('manages identity and resource grants from settings roles tab', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
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
  await expect(
    page
      .getByTestId('resource-access-form-subject-pick')
      .locator('option[value="user:user-qa"]'),
  ).toHaveCount(1)

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

test('creates edits activates and deletes a role prompt from a quick template', async ({ page }) => {
  const templateName = '代码审查专家'
  const initialName = templateName
  const editedName = 'E2E 代码审查角色'
  const editedContent = 'You are an E2E code review expert. Focus on correctness and test coverage.'

  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)
  await page.getByTestId('settings-tab-roles').click()

  const defaultPromptRow = page
    .getByTestId('settings-role-prompt-row')
    .filter({ hasText: 'AI Assistant' })
  await expect(defaultPromptRow).toBeVisible()
  await expect(defaultPromptRow.getByTestId('settings-role-prompt-delete')).toHaveCount(0)

  await page
    .getByTestId('settings-role-prompt-quick-template')
    .and(page.locator(`[data-template-name="${templateName}"]`))
    .click()
  await expect(page.getByTestId('settings-role-prompt-name')).toHaveValue(initialName)
  await page.getByTestId('settings-role-prompt-save').click()

  const createdPromptRow = page
    .getByTestId('settings-role-prompt-row')
    .filter({ hasText: initialName })
  await expect(createdPromptRow).toBeVisible()

  const promptId = await createdPromptRow.getAttribute('data-prompt-id')
  expect(promptId).toBeTruthy()

  await createdPromptRow.getByTestId('settings-role-prompt-edit').click()
  await page.getByTestId('settings-role-prompt-name').fill(editedName)
  await page.getByTestId('settings-role-prompt-content').fill(editedContent)
  await page.getByTestId('settings-role-prompt-save').click()

  const editedPromptRow = page.locator(
    `[data-testid="settings-role-prompt-row"][data-prompt-id="${promptId}"]`,
  )
  await expect(editedPromptRow).toContainText(editedName)
  await expect(editedPromptRow).toContainText(editedContent)

  await editedPromptRow.getByTestId('settings-role-prompt-activate').click()
  await expect(editedPromptRow.getByText('当前使用')).toBeVisible()

  await editedPromptRow.getByTestId('settings-role-prompt-delete').click()
  await expect(editedPromptRow).toHaveCount(0)
  await expect(defaultPromptRow).toBeVisible()
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
    .locator(`[data-testid="settings-cloud-profile-card"][data-profile-name="${profileName}"]`)
  await expect(settingsProfileCard).toContainText(profileName)
  await expect(settingsProfileCard.getByTestId('settings-cloud-profile-clear')).toBeVisible()

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
      .locator(`[data-testid="settings-cloud-profile-card"][data-profile-name="${profileName}"]`),
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
