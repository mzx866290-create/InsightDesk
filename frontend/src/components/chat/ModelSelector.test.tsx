import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ModelConfig } from '../../api/client';
import { getOllamaModels, getProviderCatalog } from '../../api/client';
import { useChatStore } from '../../stores/chatStore';
import { ModelSelector } from './ModelSelector';

vi.mock('../../api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/client')>();
  return {
    ...original,
    getOllamaModels: vi.fn(),
    getProviderCatalog: vi.fn(),
  };
});

const originalUpdatePanelModel = useChatStore.getState().updatePanelModel;
const originalOpenSettings = useChatStore.getState().openSettings;

const modelConfig: ModelConfig = {
  panel_id: 'panel-1',
  connection_type: 'openai_compatible',
  provider: 'openai_compatible',
  model: 'gpt-4o-mini',
  base_url: 'https://openrouter.ai/api/v1',
  api_key: '',
  api_key_ref: '',
  temperature: 0.3,
  agent_mode: 'auto',
};

describe('ModelSelector provider integration', () => {
  const updatePanelModel = vi.fn();
  const openSettings = vi.fn();

  beforeEach(() => {
    updatePanelModel.mockReset();
    openSettings.mockReset();
    vi.mocked(getOllamaModels).mockResolvedValue([]);
    vi.mocked(getProviderCatalog).mockResolvedValue({
      providers: [],
      default_provider: 'ollama',
      total: 0,
    });
    useChatStore.setState({
      updatePanelModel,
      openSettings,
      cloudModelProfiles: [],
      providerConfigs: [
        {
          id: 'builtin:openai_compatible',
          name: 'OpenAI GPT',
          connectionType: 'openai_compatible',
          apiKeyRef: 'managed-key-ref',
          baseUrl: 'https://gateway.example.test/v1',
          enabled: true,
          isBuiltin: true,
          createdAt: 1,
          updatedAt: 1,
        },
      ],
    });
  });

  afterEach(() => {
    cleanup();
    useChatStore.setState({
      updatePanelModel: originalUpdatePanelModel,
      openSettings: originalOpenSettings,
      cloudModelProfiles: [],
      providerConfigs: [],
      modelProviderOpen: false,
    });
    vi.clearAllMocks();
  });

  it('applies an enabled provider configuration to the active panel', async () => {
    const user = userEvent.setup();
    render(<ModelSelector panelId="panel-1" modelConfig={modelConfig} canRemove={false} />);

    await user.click(screen.getByTestId('model-selector-trigger-panel-1'));
    await user.click(
      screen.getByTestId('model-selector-provider-panel-1-builtin:openai_compatible')
    );

    expect(updatePanelModel).toHaveBeenCalledWith('panel-1', {
      connection_type: 'openai_compatible',
      provider: 'openai_compatible',
      model: 'gpt-4o-mini',
      base_url: 'https://gateway.example.test/v1',
      api_key: '',
      api_key_ref: 'managed-key-ref',
    });
  });

  it('opens the primary model settings tab from the model selector', async () => {
    const user = userEvent.setup();
    render(<ModelSelector panelId="panel-1" modelConfig={modelConfig} canRemove={false} />);

    await user.click(screen.getByTestId('model-selector-trigger-panel-1'));
    await user.click(screen.getByTestId('model-selector-provider-manager-panel-1'));

    expect(openSettings).toHaveBeenCalledWith('cloud_models');
  });
});
