import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { translations } from '../../i18n';
import { useChatStore } from '../../stores/chatStore';
import { AdminTokenPanel } from './AdminTokenPanel';

const baseProps = {
  token: '',
  saved: false,
  description: 'description',
  statusText: 'admin · local',
  onTokenChange: vi.fn(),
  onSave: vi.fn(),
  onClear: vi.fn(),
};

describe('AdminTokenPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useChatStore.setState({ language: 'zh-CN' });
  });

  afterEach(() => {
    cleanup();
  });

  it('localizes token status, actions, storage notice, and identity copy', () => {
    const zh = translations['zh-CN'];

    render(<AdminTokenPanel {...baseProps} />);

    expect(screen.getByText(zh['settings.adminToken.notSet'])).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: zh['settings.adminToken.save'] })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: zh['settings.adminToken.clear'] })
    ).toBeInTheDocument();
    expect(screen.getByText(zh['settings.adminToken.storageHint'])).toBeInTheDocument();
    expect(screen.getByTestId('admin-token-identity')).toHaveTextContent(
      `${zh['settings.adminToken.currentIdentity']}：admin · local`
    );
    expect(screen.queryByText('Not Set')).not.toBeInTheDocument();
    expect(screen.queryByText('Save Token')).not.toBeInTheDocument();
  });

  it('keeps token controls touch-friendly and preserves callbacks', () => {
    render(<AdminTokenPanel {...baseProps} token="secret" saved />);

    const input = screen.getByTestId('admin-token-input');
    fireEvent.change(input, { target: { value: 'next-secret' } });
    fireEvent.click(screen.getByTestId('admin-token-save'));
    fireEvent.click(screen.getByTestId('admin-token-clear'));

    expect(input).toHaveClass('min-h-11');
    expect(screen.getByTestId('admin-token-save')).toHaveClass('min-h-11');
    expect(screen.getByTestId('admin-token-clear')).toHaveClass('min-h-11');
    expect(baseProps.onTokenChange).toHaveBeenCalledWith('next-secret');
    expect(baseProps.onSave).toHaveBeenCalledTimes(1);
    expect(baseProps.onClear).toHaveBeenCalledTimes(1);
  });
});
