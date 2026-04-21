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
  await expect(profileCard).toContainText('Managed key linked')

  await profileCard.locator('[data-testid^="settings-cloud-profile-edit-"]').click()
  await expect(page.getByTestId('settings-cloud-profile-clear-editor')).toBeVisible()
  await expect(page.getByText('Managed key is currently linked to this profile.')).toBeVisible()

  await page.getByTestId('settings-cloud-profile-api-key-input').fill(rotatedApiKey)
  await page.getByTestId('settings-cloud-profile-save').click()

  await expect(profileCard).toContainText('Managed key linked')

  await profileCard.locator('[data-testid^="settings-cloud-profile-clear-"]').click()
  await expect(profileCard).toContainText('No managed key')

  await profileCard.locator('[data-testid^="settings-cloud-profile-delete-"]').click()
  await expect(profileCard).toHaveCount(0)
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
  await expect(settingsProfileCard).toContainText('Managed key linked')

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

test('generates a report preview from a completed research answer', async ({ page }) => {
  const query = 'Prepare a research-backed summary for agent QA'

  await generateReportFromLatestResearch(page, query)

  await expect(page.getByTestId('report-preview-content')).toContainText('Mock Research Report')
  await expect(page.getByTestId('report-preview-content')).toContainText(
    'The async task flow completed successfully.',
  )
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

