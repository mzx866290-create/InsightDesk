export type KbRetrievalMode = 'semantic' | 'keyword' | 'hybrid'

export type KbRetrievalControlsVariant = 'diagnostic' | 'tab'
export type KbFetchKVisibility = 'always' | 'rerank'
export type KbRerankPosition = 'after-mode' | 'after-numbers'

export interface KbRetrievalControlsConfig {
  controlsClassName: string
  selectClassName: string
  numberInputClassName: string
  queryInputClassName: string
  queryRowClassName: string
  modeLabel: string
  modeOptions: Record<KbRetrievalMode, string>
  rerankLabel: string
  searchKLabel: string
  fetchKLabel: string
  placeholder: string
  submitLabel: string
  fetchKVisibility: KbFetchKVisibility
  rerankPosition: KbRerankPosition
}

export const KB_RETRIEVAL_CONTROL_CONFIG: Record<KbRetrievalControlsVariant, KbRetrievalControlsConfig> = {
  diagnostic: {
    controlsClassName: 'mb-2 flex flex-wrap items-center gap-3 text-xs',
    selectClassName: 'input-base py-0.5 text-xs',
    numberInputClassName: 'input-base w-14 text-center text-xs py-0.5',
    queryInputClassName: 'input-base flex-1 text-sm',
    queryRowClassName: 'flex gap-2',
    modeLabel: '模式',
    modeOptions: {
      semantic: '仅语义',
      keyword: '仅关键词',
      hybrid: '混合',
    },
    rerankLabel: '向量 + 重排',
    searchKLabel: '检索 K',
    fetchKLabel: '召回 K',
    placeholder: '输入测试检索问题...',
    submitLabel: '测试',
    fetchKVisibility: 'rerank',
    rerankPosition: 'after-mode',
  },
  tab: {
    controlsClassName: 'flex flex-wrap items-center gap-3 rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2 text-xs',
    selectClassName: 'px-2 py-1 rounded-md bg-bg-tertiary border border-bg-border text-text-primary',
    numberInputClassName: 'w-14 px-2 py-1 rounded-md bg-bg-tertiary border border-bg-border text-center text-text-primary',
    queryInputClassName: 'flex-1 px-3 py-2 text-sm bg-bg-tertiary border border-bg-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue',
    queryRowClassName: 'flex gap-2',
    modeLabel: '模式',
    modeOptions: {
      semantic: '仅向量',
      keyword: '仅关键词',
      hybrid: '混合检索',
    },
    rerankLabel: '二段重排',
    searchKLabel: 'Top K',
    fetchKLabel: 'Fetch K',
    placeholder: '输入检索词，测试知识库召回效果...',
    submitLabel: '检索',
    fetchKVisibility: 'always',
    rerankPosition: 'after-numbers',
  },
}

export function clampKbRetrievalNumber(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

export function getKbRetrievalTestId(prefix: string | undefined, name: string) {
  return prefix ? `${prefix}-${name}` : undefined
}
