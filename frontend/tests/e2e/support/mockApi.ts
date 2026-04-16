import type { Page, Route } from '@playwright/test'

interface MockSession {
  session_id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
  is_archived: boolean
  is_favorite: boolean
  is_pinned: boolean
  session_order: number
  tags: string[]
  workspace_id: string
}

interface MockMessagesPayload {
  messages: Array<Record<string, unknown>>
  context_limit: number
  total_messages: number
  panels: Array<Record<string, unknown>>
  panel_messages: Record<string, Array<Record<string, unknown>>>
}

interface MockTask {
  task_id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result?: string
  error?: string
  params?: Record<string, unknown>
  session_id?: string | null
  created_at: number
  updated_at?: number
}

interface MockDeck {
  version: string
  deck_id: string
  status: string
  meta: {
    title: string
    subtitle: string
    language: string
    audience: string
    purpose: string
    author: string
    theme: 'default' | 'midnight' | 'sunrise'
    created_at: string
    session_id: string
    source_mode: 'kb_plus_chat' | 'chat_only'
    generator_panel_id: string
    source_answer_group_id?: string
    source_panel_id?: string
  }
  generation: {
    source: 'kb_plus_chat' | 'chat_only'
    target_slide_count: number
    actual_slide_count: number
    warnings: Array<{ code: string; message: string }>
  }
  slides: Array<{
    id: string
    type: string
    title: string
    subtitle: string
    layout: string
    intent: string
    speaker_notes: string
    blocks: Array<{
      id: string
      kind: string
      role: string
      content: {
        text?: string
        items?: string[]
      }
      editable: boolean
    }>
    evidence_refs: Array<{
      id: string
      source_id: string
      source_title: string
      excerpt_id?: string | null
      snippet: string
      confidence: number
    }>
    quality_state: 'supported' | 'weak_support' | 'manual'
    status: {
      locked: boolean
      dirty: boolean
      review_state: string
    }
  }>
  source_registry: Array<{
    id: string
    type: string
    title: string
    document_id?: string | null
    uri?: string | null
    metadata: Record<string, unknown>
  }>
}

const now = 1_710_000_000
const defaultWorkspace = {
  workspace_id: 'workspace-default',
  name: 'Default Workspace',
  description: '',
  color: 'blue',
  is_active: true,
  created_at: now,
  updated_at: now,
  session_count: 0,
}

const defaultPrompt = {
  id: 'prompt-default',
  name: 'AI Assistant',
  content: 'You are a helpful assistant.',
  is_default: true,
  is_active: true,
  created_at: now,
  updated_at: now,
}

function createMockDeck({
  deckId = 'deck-mock-1',
  title = 'Mock Deck',
  sessionId = 'session-1',
  answerGroupId = 'answer-group-1',
  panelId = 'panel-1',
}: {
  deckId?: string
  title?: string
  sessionId?: string
  answerGroupId?: string
  panelId?: string
} = {}): MockDeck {
  return {
    version: '1.0.0',
    deck_id: deckId,
    status: 'ready',
    meta: {
      title,
      subtitle: 'Generated from the research report',
      language: 'zh-CN',
      audience: 'project team',
      purpose: 'demo',
      author: 'Playwright Mock',
      theme: 'default',
      created_at: '2026-04-15T00:00:00.000Z',
      session_id: sessionId,
      source_mode: 'chat_only',
      generator_panel_id: panelId,
      source_answer_group_id: answerGroupId,
      source_panel_id: panelId,
    },
    generation: {
      source: 'chat_only',
      target_slide_count: 8,
      actual_slide_count: 2,
      warnings: [],
    },
    slides: [
      {
        id: 'slide-cover',
        type: 'cover',
        title,
        subtitle: 'Deck editor smoke coverage',
        layout: 'cover',
        intent: 'overview',
        speaker_notes: 'Opening slide for the generated deck.',
        blocks: [
          {
            id: 'block-cover-summary',
            kind: 'paragraph',
            role: 'summary',
            content: {
              text: 'This deck was generated from the mock report preview flow.',
            },
            editable: true,
          },
        ],
        evidence_refs: [
          {
            id: 'evidence-1',
            source_id: 'source-1',
            source_title: 'Research source for smoke test',
            snippet: 'Evidence collected for the deck smoke test.',
            confidence: 0.91,
          },
        ],
        quality_state: 'supported',
        status: {
          locked: false,
          dirty: false,
          review_state: 'draft',
        },
      },
      {
        id: 'slide-content',
        type: 'content',
        title: 'Mock deck overview',
        subtitle: 'Key validation points',
        layout: 'content',
        intent: 'details',
        speaker_notes: 'Second slide for editor verification.',
        blocks: [
          {
            id: 'block-content-list',
            kind: 'bullet_list',
            role: 'main_points',
            content: {
              items: [
                'Deck generation task completes successfully.',
                'Deck details are fetched through the mocked API.',
                'The deck editor opens with renderable content.',
              ],
            },
            editable: true,
          },
        ],
        evidence_refs: [],
        quality_state: 'supported',
        status: {
          locked: false,
          dirty: false,
          review_state: 'draft',
        },
      },
    ],
    source_registry: [
      {
        id: 'source-1',
        type: 'web',
        title: 'Research source for smoke test',
        uri: 'https://example.com/research-source',
        metadata: {},
      },
    ],
  }
}

function emptyMessagesPayload(): MockMessagesPayload {
  return {
    messages: [],
    context_limit: 16,
    total_messages: 0,
    panels: [],
    panel_messages: {},
  }
}

function buildResearchSources(query: string, answerGroupId?: string): Array<Record<string, unknown>> {
  return [
    {
      type: 'web',
      title: `Research source for ${query}`,
      url: 'https://example.com/research-source',
      snippet: `Evidence collected for ${query}.`,
      index: 1,
      answer_group_id: answerGroupId,
    },
  ]
}

async function fulfillJson(route: Route, payload: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(payload),
  })
}

async function fulfillSse(route: Route, body: string): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'text/event-stream; charset=utf-8',
    headers: {
      'cache-control': 'no-cache',
      connection: 'keep-alive',
    },
    body,
  })
}

export async function installAppApiMocks(page: Page): Promise<void> {
  let sessionCounter = 1
  let taskCounter = 1
  const sessions: MockSession[] = []
  const sessionMessages = new Map<string, MockMessagesPayload>()
  const tasks = new Map<string, MockTask>()
  const taskPollCounts = new Map<string, number>()
  const decks = new Map<string, MockDeck>([['deck-mock-1', createMockDeck()]])

  const ensureSessionMessages = (sessionId: string): MockMessagesPayload => {
    const existing = sessionMessages.get(sessionId)
    if (existing) return existing
    const next = emptyMessagesPayload()
    sessionMessages.set(sessionId, next)
    return next
  }

  const finalizeTask = (task: MockTask): MockTask => {
    const params = task.params ?? {}

    if (task.task_type === 'web_research') {
      const query = typeof params.query === 'string' ? params.query : 'Untitled research'
      const answerGroupId =
        typeof params.answer_group_id === 'string' ? params.answer_group_id : undefined
      return {
        ...task,
        status: 'completed',
        progress: 100,
        result: `Research summary for: ${query}`,
        params: {
          ...params,
          research_sources: buildResearchSources(query, answerGroupId),
        },
        updated_at: now + taskCounter,
      }
    }

    if (task.task_type === 'generate_report') {
      const answerGroupId =
        typeof params.answer_group_id === 'string' ? params.answer_group_id : 'unknown-answer-group'
      const panelId = typeof params.panel_id === 'string' ? params.panel_id : 'panel-1'
      return {
        ...task,
        status: 'completed',
        progress: 100,
        result: 'Report preview generated successfully.',
        params: {
          ...params,
          answer_group_id: answerGroupId,
          panel_id: panelId,
          report_title: 'Mock Research Report',
          report_markdown: [
            '# Mock Research Report',
            '',
            '## Key Findings',
            '- The async task flow completed successfully.',
            '- The report preview can be opened from the assistant message.',
          ].join('\n'),
        },
        updated_at: now + taskCounter,
      }
    }

    if (task.task_type === 'generate_deck') {
      const deckId = typeof params.deck_id === 'string' ? params.deck_id : 'deck-mock-1'
      const deckTitle = typeof params.deck_title === 'string' ? params.deck_title : 'Mock Deck'
      const answerGroupId =
        typeof params.answer_group_id === 'string' ? params.answer_group_id : 'answer-group-1'
      const panelId = typeof params.panel_id === 'string' ? params.panel_id : 'panel-1'
      decks.set(
        deckId,
        createMockDeck({
          deckId,
          title: deckTitle,
          sessionId: task.session_id ?? 'session-1',
          answerGroupId,
          panelId,
        }),
      )
      return {
        ...task,
        status: 'completed',
        progress: 100,
        result: 'Deck generated successfully.',
        params: {
          ...params,
          deck_id: deckId,
          deck_title: deckTitle,
        },
        updated_at: now + taskCounter,
      }
    }

    return {
      ...task,
      status: 'completed',
      progress: 100,
      result: task.result ?? `${task.task_type} completed successfully.`,
      updated_at: now + taskCounter,
    }
  }

  await page.route('**://*/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/workspaces') {
      await fulfillJson(route, {
        workspaces: [{ ...defaultWorkspace, session_count: sessions.length }],
        active_workspace_id: defaultWorkspace.workspace_id,
      })
      return
    }

    if (method === 'GET' && path === '/api/sessions') {
      await fulfillJson(route, { sessions })
      return
    }

    if (method === 'POST' && path === '/api/sessions') {
      const body = (request.postDataJSON() ?? {}) as {
        title?: string
        workspace_id?: string
      }
      const title =
        typeof body.title === 'string' && body.title.trim()
          ? body.title.trim()
          : '新建对话'
      const sessionId = `session-${sessionCounter}`
      sessionCounter += 1
      const session: MockSession = {
        session_id: sessionId,
        title,
        created_at: now + sessionCounter,
        updated_at: now + sessionCounter,
        message_count: 0,
        is_archived: false,
        is_favorite: false,
        is_pinned: false,
        session_order: 0,
        tags: [],
        workspace_id:
          typeof body.workspace_id === 'string' && body.workspace_id.trim()
            ? body.workspace_id.trim()
            : defaultWorkspace.workspace_id,
      }
      sessions.unshift(session)
      ensureSessionMessages(sessionId)
      await fulfillJson(route, {
        session_id: session.session_id,
        title: session.title,
        workspace_id: session.workspace_id,
      })
      return
    }

    if (method === 'GET' && path === '/api/bookmarks') {
      await fulfillJson(route, { bookmarks: [] })
      return
    }

    if (method === 'GET' && path === '/api/prompts') {
      await fulfillJson(route, { prompts: [defaultPrompt] })
      return
    }

    if (method === 'GET' && path === '/api/models/ollama') {
      await fulfillJson(route, { models: ['qwen3.5-2B:latest'] })
      return
    }

    const reportDownloadMatch = path.match(/^\/api\/reports\/download\/([^/]+)$/)
    if (method === 'GET' && reportDownloadMatch) {
      const sessionId = decodeURIComponent(reportDownloadMatch[1])
      const session = sessions.find((item) => item.session_id === sessionId)
      if (!session) {
        await fulfillJson(route, { detail: `Unknown session: ${sessionId}` }, 404)
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        body: 'mock report export',
      })
      return
    }

    const messagesMatch = path.match(/^\/api\/sessions\/([^/]+)\/messages$/)
    if (method === 'GET' && messagesMatch) {
      const sessionId = decodeURIComponent(messagesMatch[1])
      await fulfillJson(route, ensureSessionMessages(sessionId))
      return
    }

    if (method === 'POST' && path === '/api/chat/parallel') {
      const body = (request.postDataJSON() ?? {}) as {
        session_id?: string
        message?: string
        answer_group_id?: string
        models?: Array<{ panel_id?: string; model?: string }>
      }
      const prompt =
        typeof body.message === 'string' && body.message.trim()
          ? body.message.trim()
          : 'Empty prompt'
      const models =
        Array.isArray(body.models) && body.models.length > 0
          ? body.models
          : [{ panel_id: 'panel-1', model: 'qwen3.5-2B:latest' }]

      if (typeof body.session_id === 'string' && body.session_id.trim()) {
        const session = sessions.find((item) => item.session_id === body.session_id)
        if (session) {
          session.message_count = 2
          session.updated_at = now + sessionCounter
        }
        ensureSessionMessages(body.session_id)
      }

      const stream = [
        ...models.flatMap((model, index) => {
          const panelId =
            typeof model.panel_id === 'string' && model.panel_id.trim()
              ? model.panel_id
              : `panel-${index + 1}`
          return [
            `data: ${JSON.stringify({
              type: 'chunk',
              panel_id: panelId,
              answer_group_id: body.answer_group_id,
              content: `Mock answer for: ${prompt}`,
            })}`,
            `data: ${JSON.stringify({
              type: 'done',
              panel_id: panelId,
              answer_group_id: body.answer_group_id,
            })}`,
          ]
        }),
        `data: ${JSON.stringify({ type: 'all_done' })}`,
      ].join('\n\n') + '\n\n'

      await fulfillSse(route, stream)
      return
    }

    if (method === 'POST' && path === '/api/tasks') {
      const body = (request.postDataJSON() ?? {}) as {
        task_type?: string
        params?: Record<string, unknown>
        session_id?: string
      }
      const taskId = `task-${taskCounter}`
      taskCounter += 1
      const task: MockTask = {
        task_id: taskId,
        task_type:
          typeof body.task_type === 'string' && body.task_type.trim()
            ? body.task_type.trim()
            : 'task',
        status: 'pending',
        progress: 5,
        params: body.params ?? {},
        session_id:
          typeof body.session_id === 'string' && body.session_id.trim()
            ? body.session_id.trim()
            : null,
        created_at: now + taskCounter,
        updated_at: now + taskCounter,
      }
      tasks.set(taskId, task)
      taskPollCounts.set(taskId, 0)
      await fulfillJson(route, task)
      return
    }

    const taskMatch = path.match(/^\/api\/tasks\/([^/]+)$/)
    if (method === 'GET' && taskMatch) {
      const taskId = decodeURIComponent(taskMatch[1])
      const existing = tasks.get(taskId)
      if (!existing) {
        await fulfillJson(route, { detail: `Unknown task: ${taskId}` }, 404)
        return
      }

      const pollCount = (taskPollCounts.get(taskId) ?? 0) + 1
      taskPollCounts.set(taskId, pollCount)

      const nextTask =
        existing.status === 'pending' || existing.status === 'running'
          ? finalizeTask(existing)
          : existing
      tasks.set(taskId, nextTask)
      await fulfillJson(route, nextTask)
      return
    }

    const regenerateDeckSlideMatch = path.match(/^\/api\/decks\/([^/]+)\/slides\/([^/]+)\/regenerate$/)
    if (method === 'POST' && regenerateDeckSlideMatch) {
      const deckId = decodeURIComponent(regenerateDeckSlideMatch[1])
      const slideId = decodeURIComponent(regenerateDeckSlideMatch[2])
      const existing = decks.get(deckId)
      if (!existing) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }

      const nextDeck: MockDeck = {
        ...existing,
        slides: existing.slides.map((slide) =>
          slide.id === slideId
            ? {
                ...slide,
                title: `${slide.title} (Regenerated)`,
                blocks: slide.blocks.map((block, index) =>
                  index === 0 && block.kind === 'paragraph'
                    ? {
                        ...block,
                        content: {
                          ...block.content,
                          text: 'This slide was regenerated by the mock API.',
                        },
                      }
                    : block,
                ),
                status: {
                  ...slide.status,
                  dirty: false,
                },
              }
            : slide,
        ),
      }
      decks.set(deckId, nextDeck)
      await fulfillJson(route, nextDeck)
      return
    }

    const exportDeckMatch = path.match(/^\/api\/decks\/([^/]+)\/export$/)
    if (method === 'GET' && exportDeckMatch) {
      const deckId = decodeURIComponent(exportDeckMatch[1])
      if (!decks.has(deckId)) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        body: 'mock deck export',
      })
      return
    }

    const deckShareMatch = path.match(/^\/api\/decks\/([^/]+)\/share$/)
    if (method === 'POST' && deckShareMatch) {
      const deckId = decodeURIComponent(deckShareMatch[1])
      if (!decks.has(deckId)) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }
      await fulfillJson(route, {
        resource_type: 'deck',
        resource_id: deckId,
        share_token: 'share-token-mock',
        share_url: `https://example.com/shared/decks/${deckId}`,
      })
      return
    }

    const deckMatch = path.match(/^\/api\/decks\/([^/]+)$/)
    if (deckMatch) {
      const deckId = decodeURIComponent(deckMatch[1])
      const existing = decks.get(deckId)
      if (!existing) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }

      if (method === 'GET') {
        await fulfillJson(route, existing)
        return
      }

      if (method === 'PATCH') {
        const body = (request.postDataJSON() ?? {}) as {
          title?: string
          theme?: 'default' | 'midnight' | 'sunrise'
          slides?: MockDeck['slides']
        }
        const nextDeck: MockDeck = {
          ...existing,
          meta: {
            ...existing.meta,
            title: typeof body.title === 'string' ? body.title : existing.meta.title,
            theme: body.theme ?? existing.meta.theme,
          },
          slides: Array.isArray(body.slides) ? body.slides : existing.slides,
        }
        decks.set(deckId, nextDeck)
        await fulfillJson(route, nextDeck)
        return
      }
    }

    if (method === 'GET' && path === '/api/tasks') {
      const limitRaw = url.searchParams.get('limit')
      const limit = limitRaw ? Number(limitRaw) : 20
      const taskList = [...tasks.values()]
        .sort((a, b) => (b.updated_at ?? b.created_at) - (a.updated_at ?? a.created_at))
        .slice(0, Number.isFinite(limit) ? limit : 20)
      await fulfillJson(route, { tasks: taskList })
      return
    }

    await fulfillJson(
      route,
      { detail: `Unhandled mock route: ${method} ${path}` },
      404,
    )
  })
}
