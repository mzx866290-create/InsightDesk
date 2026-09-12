import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useChatStore } from '../../stores/chatStore';
import { GeneralSettingsPanel, type GeneralSettingsPanelProps } from './GeneralSettingsPanel';

const props: GeneralSettingsPanelProps = {
  language: 'en-US',
  adminToken: '',
  adminTokenSaved: false,
  adminAccessError: null,
  authStatusText: null,
  tavilyKey: '',
  tavilyKeySet: false,
  saving: false,
  saveOk: false,
  saveError: null,
  resetting: false,
  onLanguageChange: vi.fn(),
  onAdminTokenChange: vi.fn(),
  onSaveAdminToken: vi.fn(),
  onClearAdminToken: vi.fn(),
  onTavilyKeyChange: vi.fn(),
  onSaveGeneral: vi.fn(),
  onClearTavilyKey: vi.fn(),
  onResetAgents: vi.fn(),
};

describe('GeneralSettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useChatStore.setState({ language: 'en-US' });
  });

  afterEach(() => {
    cleanup();
  });

  it('keeps the agent cache reset action at least 44px tall', () => {
    render(<GeneralSettingsPanel {...props} />);

    expect(screen.queryByText('Manage Model Providers')).not.toBeInTheDocument();
    const resetButton = screen.getByTestId('settings-reset-agents');
    expect(resetButton).toHaveClass('min-h-11');

    fireEvent.click(resetButton);
    expect(props.onResetAgents).toHaveBeenCalledTimes(1);
  });
});
