import type { DeckBlock, DeckEvidenceRef, DeckSlide, DeckSpec } from '../../api/client'

type DeckTheme = DeckSpec['meta']['theme']

const DECK_THEME_LABELS: Record<DeckTheme, string> = {
  default: '经典蓝图',
  midnight: '深夜简报',
  sunrise: '晨曦回顾',
}

const SLIDE_TYPE_LABELS: Record<string, string> = {
  cover: '封面页',
  agenda: '目录页',
  section: '章节页',
  content: '内容页',
  summary: '总结页',
  closing: '结尾页',
}

const SLIDE_LAYOUT_LABELS: Record<string, string> = {
  cover: '封面',
  agenda: '目录',
  section: '章节',
  content: '内容',
  two_column: '双栏',
  comparison: '对比',
  timeline: '时间线',
  closing: '结尾',
}

const QUALITY_LABELS: Record<string, string> = {
  supported: '证据充分',
  manual: '需人工确认',
  draft: '草稿',
}

const PRINT_THEME_TOKENS: Record<DeckTheme, {
  pageBg: string
  surface: string
  surfaceAlt: string
  border: string
  title: string
  body: string
  muted: string
  accent: string
}> = {
  default: {
    pageBg: '#f3f6fb',
    surface: '#ffffff',
    surfaceAlt: '#eef4ff',
    border: '#d8e0ee',
    title: '#162033',
    body: '#2a3547',
    muted: '#60708a',
    accent: '#2563eb',
  },
  midnight: {
    pageBg: '#020617',
    surface: '#111827',
    surfaceAlt: '#1e293b',
    border: '#334155',
    title: '#f8fafc',
    body: '#e2e8f0',
    muted: '#94a3b8',
    accent: '#38bdf8',
  },
  sunrise: {
    pageBg: '#fff7ed',
    surface: '#fffbf5',
    surfaceAlt: '#fde7d6',
    border: '#f4c7a1',
    title: '#7c2d12',
    body: '#9a3412',
    muted: '#c2410c',
    accent: '#ea580c',
  },
}

function yamlString(value: string): string {
  return JSON.stringify(value ?? '')
}

function cleanText(value: string | undefined | null): string {
  return (value ?? '').trim()
}

function escapeHtml(value: string | undefined | null): string {
  return cleanText(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function deckThemeLabel(theme: DeckTheme): string {
  return DECK_THEME_LABELS[theme] ?? theme
}

function slideTypeLabel(value: string): string {
  return SLIDE_TYPE_LABELS[value] ?? value
}

function slideLayoutLabel(value: string): string {
  return SLIDE_LAYOUT_LABELS[value] ?? value
}

function qualityLabel(value: string): string {
  return QUALITY_LABELS[value] ?? value
}

function sourceModeLabel(value: string): string {
  return value === 'kb_plus_chat' ? '知识库 + 聊天' : value === 'chat_only' ? '仅聊天' : value
}

function renderBulletList(block: DeckBlock): string {
  const items = (block.content.items ?? [])
    .map((item) => cleanText(item))
    .filter(Boolean)

  return items.map((item) => `- ${item}`).join('\n')
}

function renderTextBlock(block: DeckBlock): string {
  return cleanText(block.content.text)
}

function renderBlock(block: DeckBlock): string {
  const body =
    block.kind === 'bullet_list'
      ? renderBulletList(block)
      : renderTextBlock(block)

  if (!body) return ''
  if (!block.role || block.role === 'body') return body

  return `### ${block.role}\n\n${body}`
}

function renderEvidenceRefs(evidenceRefs: DeckEvidenceRef[]): string {
  if (evidenceRefs.length === 0) return ''

  const items = evidenceRefs.map((evidence) => {
    const confidence =
      typeof evidence.confidence === 'number' && evidence.confidence > 0
        ? ` (${Math.round(evidence.confidence * 100)}%)`
        : ''
    const snippet = cleanText(evidence.snippet)
    return `- **${evidence.source_title}**${confidence}: ${snippet || '无摘要'}`
  })

  return ['### 证据引用', '', ...items].join('\n')
}

function renderSpeakerNotes(slide: DeckSlide): string {
  const notes = cleanText(slide.speaker_notes)
  if (!notes) return ''

  return ['### 演讲备注', '', notes].join('\n')
}

function renderSlide(slide: DeckSlide): string {
  const parts: string[] = [
    `<!-- ${JSON.stringify({
      slide_id: slide.id,
      type: slide.type,
      layout: slide.layout,
      intent: slide.intent,
      quality_state: slide.quality_state,
    })} -->`,
    `# ${cleanText(slide.title) || '未命名页面'}`,
  ]

  const subtitle = cleanText(slide.subtitle)
  if (subtitle) {
    parts.push('', `> ${subtitle}`)
  }

  const blockSections = slide.blocks
    .map((block) => renderBlock(block))
    .filter(Boolean)
  if (blockSections.length > 0) {
    parts.push('', blockSections.join('\n\n'))
  }

  const evidence = renderEvidenceRefs(slide.evidence_refs)
  if (evidence) {
    parts.push('', evidence)
  }

  const notes = renderSpeakerNotes(slide)
  if (notes) {
    parts.push('', notes)
  }

  return parts.join('\n')
}

export function buildDeckMarkdown(deck: DeckSpec): string {
  const frontmatter = [
    '---',
    `title: ${yamlString(cleanText(deck.meta.title) || '演示稿草稿')}`,
    `theme: ${cleanText(deck.meta.theme) || 'default'}`,
    `author: ${yamlString(cleanText(deck.meta.author) || 'AI 智能体')}`,
    `deck_id: ${yamlString(deck.deck_id)}`,
    `source_mode: ${yamlString(deck.meta.source_mode)}`,
    `generator_panel_id: ${yamlString(deck.meta.generator_panel_id)}`,
    `created_at: ${yamlString(deck.meta.created_at)}`,
    '---',
  ].join('\n')

  const slides = deck.slides.map((slide) => renderSlide(slide))
  return [frontmatter, ...slides].join('\n\n---\n\n')
}

export function buildDeckDownloadFilename(title: string, extension: string): string {
  const normalizedExtension = extension.replace(/^\./, '')
  const safeTitle = cleanText(title)
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 40)

  return `${safeTitle || '演示稿'}.${normalizedExtension || 'txt'}`
}

function renderBlockHtml(block: DeckBlock): string {
  if (block.kind === 'bullet_list') {
    const items = (block.content.items ?? [])
      .map((item) => cleanText(item))
      .filter(Boolean)
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join('')
    if (!items) return ''
    return `<ul class="deck-list">${items}</ul>`
  }

  const text = cleanText(block.content.text)
  if (!text) return ''
  return `<p class="deck-paragraph">${escapeHtml(text).replace(/\n/g, '<br />')}</p>`
}

function renderEvidenceHtml(evidenceRefs: DeckEvidenceRef[]): string {
  if (evidenceRefs.length === 0) return ''
  const items = evidenceRefs
    .map((evidence) => {
      const confidence =
        typeof evidence.confidence === 'number' && evidence.confidence > 0
          ? ` (${Math.round(evidence.confidence * 100)}%)`
          : ''
      return `
        <li>
          <strong>${escapeHtml(evidence.source_title)}</strong>${escapeHtml(confidence)}
          <div class="deck-evidence-snippet">${escapeHtml(evidence.snippet || '暂无摘要')}</div>
        </li>
      `
    })
    .join('')
  return `
    <section class="deck-evidence">
      <div class="deck-section-label">证据引用</div>
      <ul>${items}</ul>
    </section>
  `
}

export function buildDeckPrintHtml(deck: DeckSpec): string {
  const theme = PRINT_THEME_TOKENS[deck.meta.theme ?? 'default'] ?? PRINT_THEME_TOKENS.default
  const slides = deck.slides
    .map((slide, index) => {
      const blocks = slide.blocks
        .map((block) => renderBlockHtml(block))
        .filter(Boolean)
        .join('')
      const subtitle = cleanText(slide.subtitle)
      const notes = cleanText(slide.speaker_notes)
      return `
        <section class="slide-page">
          <div class="slide-shell">
            <header class="slide-header">
              <div>
                <div class="slide-layout">${escapeHtml(slideLayoutLabel(slide.layout || slide.type))}</div>
                <h1>${escapeHtml(slide.title || '未命名页面')}</h1>
                ${subtitle ? `<p class="slide-subtitle">${escapeHtml(subtitle)}</p>` : ''}
              </div>
              <div class="slide-badge">${escapeHtml(qualityLabel(slide.quality_state))}</div>
            </header>

            <main class="slide-body">
              ${blocks || '<p class="deck-empty">暂无内容。</p>'}
              ${renderEvidenceHtml(slide.evidence_refs)}
            </main>

            <footer class="slide-footer">
              <div>${escapeHtml(sourceModeLabel(deck.meta.source_mode))} | ${escapeHtml(slideTypeLabel(slide.type))}</div>
              <div>${index + 1} / ${deck.slides.length}</div>
            </footer>

            ${notes ? `<section class="slide-notes"><div class="deck-section-label">演讲备注</div><p>${escapeHtml(notes).replace(/\n/g, '<br />')}</p></section>` : ''}
          </div>
        </section>
      `
    })
    .join('')

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(deck.meta.title || '演示稿')}</title>
    <style>
      :root {
        --page-bg: ${theme.pageBg};
        --surface: ${theme.surface};
        --surface-alt: ${theme.surfaceAlt};
        --border: ${theme.border};
        --title: ${theme.title};
        --body: ${theme.body};
        --muted: ${theme.muted};
        --accent: ${theme.accent};
      }
      * { box-sizing: border-box; }
      html, body { margin: 0; padding: 0; background: var(--page-bg); color: var(--body); font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }
      body { padding: 24px; }
      .slide-page { break-after: page; page-break-after: always; padding: 12px 0; }
      .slide-page:last-child { break-after: auto; page-break-after: auto; }
      .slide-shell {
        width: 1280px;
        min-height: 720px;
        margin: 0 auto;
        background: linear-gradient(180deg, var(--surface), var(--surface-alt));
        border: 1px solid var(--border);
        border-radius: 28px;
        padding: 40px 44px;
        display: flex;
        flex-direction: column;
        gap: 24px;
      }
      .slide-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
      .slide-layout { font-size: 11px; letter-spacing: 0.24em; text-transform: uppercase; color: var(--accent); margin-bottom: 12px; font-weight: 700; }
      h1 { margin: 0; color: var(--title); font-size: 34px; line-height: 1.15; }
      .slide-subtitle { margin: 14px 0 0; color: var(--muted); font-size: 18px; line-height: 1.6; }
      .slide-badge { border: 1px solid var(--border); color: var(--accent); border-radius: 999px; padding: 7px 12px; font-size: 12px; text-transform: uppercase; }
      .slide-body { display: grid; gap: 16px; flex: 1; align-content: start; }
      .deck-list, .deck-evidence ul { margin: 0; padding-left: 22px; }
      .deck-list li, .deck-evidence li { margin: 0 0 10px; line-height: 1.7; }
      .deck-paragraph { margin: 0; line-height: 1.8; }
      .deck-empty { margin: 0; color: var(--muted); }
      .deck-evidence, .slide-notes { background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 16px 18px; }
      .deck-section-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent); font-weight: 700; margin-bottom: 10px; }
      .deck-evidence-snippet { color: var(--muted); margin-top: 4px; font-size: 13px; line-height: 1.6; }
      .slide-footer { display: flex; justify-content: space-between; gap: 12px; padding-top: 12px; border-top: 1px solid var(--border); color: var(--muted); font-size: 12px; }
      .slide-notes p { margin: 0; line-height: 1.7; }
      @page { size: A4 landscape; margin: 10mm; }
      @media print {
        body { padding: 0; background: white; }
        .slide-page { padding: 0; }
        .slide-shell {
          width: 100%;
          min-height: auto;
          border-radius: 0;
          box-shadow: none;
        }
      }
    </style>
  </head>
  <body>${slides}</body>
</html>`
}
