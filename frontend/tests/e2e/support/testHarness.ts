import { expect, test as base } from '@playwright/test'
import type { Page } from '@playwright/test'

import { installAppApiMocks } from './mockApi'

const test = base.extend({
  page: async ({ page, context }, use) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await installAppApiMocks(page)
    await use(page)
  },
})

export { expect, test }

export async function startResearch(page: Page, query: string): Promise<void> {
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

export async function generateReportFromLatestResearch(page: Page, query: string): Promise<void> {
  await startResearch(page, query)
  await page.getByTestId('message-generate-report').last().click()
  await expect(page.getByTestId('report-generation-modal')).toBeVisible()
  await page.getByText('Executive Report').click()
  await page.getByTestId('report-generation-submit').click()
  await expect(page.getByTestId('task-progress-card').last()).toHaveAttribute(
    'data-task-type',
    'generate_report',
  )
  await expect(page.getByTestId('report-preview-modal')).toBeVisible()
}

export async function openDeckEditorFromLatestResearch(page: Page, query: string): Promise<void> {
  await generateReportFromLatestResearch(page, query)
  await page.getByTestId('report-generate-deck').click()
  await expect(page.getByTestId('deck-generation-modal')).toBeVisible()
  await page.getByTestId('deck-generation-submit').click()
  await expect(
    page.locator('[data-testid="task-progress-card"][data-task-type="generate_deck"]'),
  ).toBeVisible()
  await expect(page.getByTestId('deck-editor-modal')).toBeVisible()
}

export async function allowDeckRiskyExport(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.confirm = () => true
  })
}

export async function mockDeckPdfPrintWindow(page: Page): Promise<void> {
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

export async function mockReportSlidevWindow(page: Page): Promise<void> {
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

export async function openAdvancedSettings(page: Page): Promise<void> {
  const advancedToggle = page.getByTestId('settings-advanced-toggle')
  await expect(advancedToggle).toBeVisible()

  if ((await advancedToggle.getAttribute('aria-expanded')) !== 'true') {
    await advancedToggle.click()
  }

  await expect(advancedToggle).toHaveAttribute('aria-expanded', 'true')
}

export async function openKnowledgeBaseMonitor(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByTestId('header-open-settings').click()
  await openAdvancedSettings(page)

  const healthResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/knowledge-base/health'),
  )
  const chunksResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/knowledge-base/chunks'),
  )

  await page.getByTestId('settings-tab-kb_monitor').click()

  const [healthResponse, chunksResponse] = await Promise.all([
    healthResponsePromise,
    chunksResponsePromise,
  ])
  expect(healthResponse.ok()).toBeTruthy()
  expect(chunksResponse.ok()).toBeTruthy()
  await expect(page.getByTestId('settings-kb-monitor-panel')).toBeVisible()
}
