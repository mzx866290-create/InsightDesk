import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CloudModelProfile } from '../../stores/chatStore'
import { useChatStore } from '../../stores/chatStore'
import { CloudModelProfilesPanel } from './CloudModelProfilesPanel'

const apiMocks = vi.hoisted(() => ({
  saveCloudModelApiKey: vi.fn(),
  deleteCloudModelApiKey: vi.fn(),
}))

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>()
  return {
    ...actual,
    saveCloudModelApiKey: apiMocks.saveCloudModelApiKey,
    deleteCloudModelApiKey: apiMocks.deleteCloudModelApiKey,
  }
})

describe('CloudModelProfilesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useChatStore.setState({
      language: 'zh-CN',
      cloudModelProfiles: [],
    })
    apiMocks.saveCloudModelApiKey.mockResolvedValue({ api_key_ref: 'managed-key-ref' })
  })

  afterEach(() => {
    cleanup()
  })

  it('renders localized cloud profile copy without hardcoded garbled text', () => {
    render(<CloudModelProfilesPanel />)

    expect(screen.getByText('云端模型配置')).toBeInTheDocument()
    expect(screen.getByText('还没有已保存的云端模型配置。可先在这里保存，再到聊天模型选择器中复用。')).toBeInTheDocument()
    expect(screen.queryByText(/褰|鍓|宸|娓|缂|鍒|杩|涔/)).not.toBeInTheDocument()
  })

  it('saves a cloud profile from the unified form state', async () => {
    render(<CloudModelProfilesPanel />)

    fireEvent.change(screen.getByTestId('settings-cloud-profile-name-input'), {
      target: { value: 'Prod OpenRouter' },
    })
    fireEvent.change(screen.getByTestId('settings-cloud-profile-model-input'), {
      target: { value: 'openai/gpt-4.1' },
    })
    fireEvent.change(screen.getByTestId('settings-cloud-profile-base-url-input'), {
      target: { value: 'https://openrouter.ai/api/v1' },
    })
    fireEvent.change(screen.getByTestId('settings-cloud-profile-api-key-input'), {
      target: { value: 'sk-test' },
    })

    fireEvent.click(screen.getByTestId('settings-cloud-profile-save'))

    const savedCard = await screen.findByTestId('settings-cloud-profile-card')

    expect(apiMocks.saveCloudModelApiKey).toHaveBeenCalledWith({
      api_key: 'sk-test',
      api_key_ref: undefined,
    })
    expect(savedCard).toHaveAttribute('data-profile-name', 'Prod OpenRouter')
    expect(within(savedCard).getByText('openai/gpt-4.1')).toBeInTheDocument()
    expect(within(savedCard).getByText('已关联托管密钥')).toBeInTheDocument()
  })

  it('shows managed key status and actions from localized labels', () => {
    const profile: CloudModelProfile = {
      id: 'profile-1',
      name: 'Prod',
      modelConfig: {
        panel_id: 'profile-1',
        connection_type: 'openai_compatible',
        provider: 'openai_compatible',
        model: 'openai/gpt-4.1',
        base_url: 'https://openrouter.ai/api/v1',
        api_key: '',
        api_key_ref: 'managed-key-ref',
        temperature: 0.3,
        agent_mode: 'auto',
      },
      createdAt: 1,
      updatedAt: 2,
    }
    useChatStore.setState({
      language: 'zh-CN',
      cloudModelProfiles: [profile],
    })

    render(<CloudModelProfilesPanel />)

    const savedCard = screen.getByTestId('settings-cloud-profile-card')
    expect(within(savedCard).getByText('已关联托管密钥')).toBeInTheDocument()
    expect(within(savedCard).getByText('清除密钥')).toBeInTheDocument()
    expect(within(savedCard).getByText('编辑')).toBeInTheDocument()
    expect(within(savedCard).getByText('删除')).toBeInTheDocument()
  })
})
