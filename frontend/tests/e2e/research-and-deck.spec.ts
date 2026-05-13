import { expect, test, startResearch, generateReportFromLatestResearch, openDeckEditorFromLatestResearch, allowDeckRiskyExport, mockDeckPdfPrintWindow, mockReportSlidevWindow } from './support/testHarness'
import { Buffer } from 'node:buffer'

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
  await expect(page.getByTestId('report-preview-content')).toContainText(
    'Template selected: executive_report.',
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
