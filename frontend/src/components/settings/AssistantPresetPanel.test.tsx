import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  activateAssistantPreset,
  createAssistantPreset,
  deleteAssistantPreset,
  getAssistantPresets,
  updateAssistantPreset,
  type AssistantPreset,
  type ModelConfig,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { defaultModelConfig } from '../../stores/chatStoreModel'
import { AssistantPresetPanel } from './AssistantPresetPanel'

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>()
  return {
    ...actual,
    activateAssistantPreset: vi.fn(),
    createAssistantPreset: vi.fn(),
    deleteAssistantPreset: vi.fn(),
    getAssistantPresets: vi.fn(),
    updateAssistantPreset: vi.fn(),
  }
})

const originalStoreActions = {
  setActiveAssistantPresetId: useChatStore.getState().setActiveAssistantPresetId,
  setActivePromptId: useChatStore.getState().setActivePromptId,
  setWebSearchEnabled: useChatStore.getState().setWebSearchEnabled,
  setKnowledgeBaseEnabled: useChatStore.getState().setKnowledgeBaseEnabled,
  setEnabledMcpServers: useChatStore.getState().setEnabledMcpServers,
  updatePanelModel: useChatStore.getState().updatePanelModel,
}

function makePreset(
  patch: Partial<AssistantPreset> & Pick<AssistantPreset, 'id' | 'name'>,
): AssistantPreset {
  return {
    id: patch.id,
    name: patch.name,
    avatar: patch.avatar ?? '🤖',
    system_prompt_id: patch.system_prompt_id ?? '',
    default_model_config: patch.default_model_config ?? defaultModelConfig('preset-panel'),
    tool_config: patch.tool_config ?? {
      web_search_enabled: false,
      knowledge_base_enabled: true,
      mcp_servers_enabled: [],
    },
    starters: patch.starters ?? [],
    is_default: patch.is_default ?? false,
    is_active: patch.is_active ?? false,
    created_at: patch.created_at ?? 1,
    updated_at: patch.updated_at ?? 1,
  }
}

describe('AssistantPresetPanel', () => {
  const getAssistantPresetsMock = vi.mocked(getAssistantPresets)
  const createAssistantPresetMock = vi.mocked(createAssistantPreset)
  const activateAssistantPresetMock = vi.mocked(activateAssistantPreset)
  const deleteAssistantPresetMock = vi.mocked(deleteAssistantPreset)
  const updateAssistantPresetMock = vi.mocked(updateAssistantPreset)

  beforeEach(() => {
    vi.clearAllMocks()
    getAssistantPresetsMock.mockResolvedValue([
      makePreset({
        id: 'preset-research',
        name: '研究助手',
        system_prompt_id: 'prompt-research',
        default_model_config: {
          ...defaultModelConfig('preset-research-panel'),
          model: 'qwen-research',
        },
        tool_config: {
          web_search_enabled: true,
          knowledge_base_enabled: true,
          mcp_servers_enabled: [],
        },
        is_active: true,
      }),
    ])
    createAssistantPresetMock.mockResolvedValue(makePreset({ id: 'preset-created', name: '代码助手' }))
    activateAssistantPresetMock.mockResolvedValue({ ok: true })
    deleteAssistantPresetMock.mockResolvedValue(undefined)
    updateAssistantPresetMock.mockResolvedValue(makePreset({ id: 'preset-research', name: '研究助手' }))

    useChatStore.setState({
      activeAssistantPresetId: null,
      panels: [
        {
          id: 'panel-live',
          modelConfig: {
            ...defaultModelConfig('panel-live'),
            model: 'qwen-live',
          },
          messages: [],
        },
      ],
      ...originalStoreActions,
    })
  })

  afterEach(() => {
    cleanup()
    useChatStore.setState({
      activeAssistantPresetId: null,
      panels: [
        {
          id: 'panel-reset',
          modelConfig: defaultModelConfig('panel-reset'),
          messages: [],
        },
      ],
      ...originalStoreActions,
    })
  })

  it('loads presets and syncs the active preset id', async () => {
    render(<AssistantPresetPanel />)

    expect(await screen.findByText('研究助手')).toBeInTheDocument()
    await waitFor(() => {
      expect(useChatStore.getState().activeAssistantPresetId).toBe('preset-research')
    })
  })

  it('creates a preset from the current panel and parsed tool fields', async () => {
    render(<AssistantPresetPanel />)

    fireEvent.change(screen.getByLabelText('Assistant preset name'), {
      target: { value: '代码助手' },
    })
    fireEvent.change(screen.getByLabelText('Assistant preset system prompt id'), {
      target: { value: 'prompt-code' },
    })
    fireEvent.change(screen.getByLabelText('Assistant preset starters'), {
      target: { value: '解释这段代码\n生成测试' },
    })
    fireEvent.click(screen.getByLabelText('Enable web search by default'))
    fireEvent.click(screen.getByLabelText('Enable knowledge base by default'))
    fireEvent.change(screen.getByLabelText('Assistant preset MCP servers'), {
      target: { value: 'github, jira' },
    })
    fireEvent.click(screen.getByLabelText('Save assistant preset'))

    await waitFor(() => {
      expect(createAssistantPresetMock).toHaveBeenCalledTimes(1)
    })
    expect(createAssistantPresetMock).toHaveBeenCalledWith(
      expect.objectContaining({
        name: '代码助手',
        system_prompt_id: 'prompt-code',
        default_model_config: expect.objectContaining({
          panel_id: 'panel-live',
          model: 'qwen-live',
        }),
        tool_config: {
          web_search_enabled: true,
          knowledge_base_enabled: false,
          mcp_servers_enabled: ['github', 'jira'],
        },
        starters: ['解释这段代码', '生成测试'],
      }),
    )
  })

  it('applies a preset to store model, prompt, and tool state', async () => {
    const setActivePromptId = vi.fn<(id: string | null) => void>()
    const setWebSearchEnabled = vi.fn<(enabled: boolean) => void>()
    const setKnowledgeBaseEnabled = vi.fn<(enabled: boolean) => void>()
    const setEnabledMcpServers = vi.fn<(servers: string[]) => void>()
    const updatePanelModel = vi.fn<(panelId: string, config: Partial<ModelConfig>) => void>()

    useChatStore.setState({
      setActivePromptId,
      setWebSearchEnabled,
      setKnowledgeBaseEnabled,
      setEnabledMcpServers,
      updatePanelModel,
    })

    render(<AssistantPresetPanel />)
    fireEvent.click(await screen.findByLabelText('Apply assistant preset 研究助手'))

    await waitFor(() => {
      expect(activateAssistantPresetMock).toHaveBeenCalledWith('preset-research')
    })
    expect(setActivePromptId).toHaveBeenCalledWith('prompt-research')
    expect(setWebSearchEnabled).toHaveBeenCalledWith(true)
    expect(setKnowledgeBaseEnabled).toHaveBeenCalledWith(true)
    expect(setEnabledMcpServers).toHaveBeenCalledWith([])
    expect(updatePanelModel).toHaveBeenCalledWith(
      'panel-live',
      expect.objectContaining({
        panel_id: 'panel-live',
        model: 'qwen-research',
      }),
    )
  })
})
