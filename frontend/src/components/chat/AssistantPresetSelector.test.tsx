import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  activateAssistantPreset,
  getAssistantPresets,
  type AssistantPreset,
  type ModelConfig,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { defaultModelConfig } from '../../stores/chatStoreModel'
import { AssistantPresetSelector } from './AssistantPresetSelector'

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>()
  return {
    ...actual,
    activateAssistantPreset: vi.fn(),
    getAssistantPresets: vi.fn(),
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

describe('AssistantPresetSelector', () => {
  const getAssistantPresetsMock = vi.mocked(getAssistantPresets)
  const activateAssistantPresetMock = vi.mocked(activateAssistantPreset)

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
      makePreset({
        id: 'preset-code',
        name: '代码助手',
        system_prompt_id: 'prompt-code',
        default_model_config: {
          ...defaultModelConfig('preset-code-panel'),
          model: 'deepseek-chat',
          connection_type: 'deepseek',
          provider: 'deepseek',
        },
        tool_config: {
          web_search_enabled: false,
          knowledge_base_enabled: false,
          mcp_servers_enabled: ['github'],
        },
      }),
    ])
    activateAssistantPresetMock.mockResolvedValue({ ok: true })
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

  it('loads the active preset name before the menu is opened', async () => {
    useChatStore.setState({ activeAssistantPresetId: 'preset-research' })

    render(<AssistantPresetSelector />)

    expect(await screen.findByText('研究助手')).toBeInTheDocument()
    expect(getAssistantPresetsMock).toHaveBeenCalledTimes(1)
  })

  it('activates the selected preset and applies its model and tools', async () => {
    const setActiveAssistantPresetId = vi.fn<(id: string | null) => void>()
    const setActivePromptId = vi.fn<(id: string | null) => void>()
    const setWebSearchEnabled = vi.fn<(enabled: boolean) => void>()
    const setKnowledgeBaseEnabled = vi.fn<(enabled: boolean) => void>()
    const setEnabledMcpServers = vi.fn<(servers: string[]) => void>()
    const updatePanelModel = vi.fn<(panelId: string, config: Partial<ModelConfig>) => void>()

    useChatStore.setState({
      activeAssistantPresetId: 'preset-research',
      panels: [
        {
          id: 'panel-live',
          modelConfig: defaultModelConfig('panel-live'),
          messages: [],
        },
      ],
      setActiveAssistantPresetId,
      setActivePromptId,
      setWebSearchEnabled,
      setKnowledgeBaseEnabled,
      setEnabledMcpServers,
      updatePanelModel,
    })

    render(<AssistantPresetSelector />)
    fireEvent.click(await screen.findByRole('button', { name: /研究助手/ }))
    fireEvent.click(await screen.findByText('代码助手'))

    await waitFor(() => {
      expect(activateAssistantPresetMock).toHaveBeenCalledWith('preset-code')
    })
    expect(setActiveAssistantPresetId).toHaveBeenCalledWith('preset-code')
    expect(setActivePromptId).toHaveBeenCalledWith('prompt-code')
    expect(setWebSearchEnabled).toHaveBeenCalledWith(false)
    expect(setKnowledgeBaseEnabled).toHaveBeenCalledWith(false)
    expect(setEnabledMcpServers).toHaveBeenCalledWith(['github'])
    expect(updatePanelModel).toHaveBeenCalledWith(
      'panel-live',
      expect.objectContaining({
        panel_id: 'panel-live',
        model: 'deepseek-chat',
        provider: 'deepseek',
      }),
    )
  })
})
