import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SettingsNavigation, type SettingsNavigationProps } from './SettingsNavigation';

const baseProps: SettingsNavigationProps = {
  activeTab: 'general',
  primaryTabs: [
    ['general', '通用设置'],
    ['assistant_presets', '助手预设'],
  ],
  advancedTabs: [
    ['sso', '单点登录'],
    ['traces', '链路追踪'],
  ],
  advancedVisible: false,
  dailyTitle: '日常配置',
  dailyDescription: '高频设置',
  advancedTitle: '高级与运维',
  advancedDescription: '管理员能力',
  advancedCollapsedHint: '默认收起',
  onSelectTab: vi.fn(),
  onToggleAdvanced: vi.fn(),
};

describe('SettingsNavigation', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('keeps low-frequency tabs collapsed until advanced settings are expanded', () => {
    const { rerender } = render(<SettingsNavigation {...baseProps} />);

    expect(screen.queryByTestId('settings-tab-sso')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('settings-advanced-toggle'));
    expect(baseProps.onToggleAdvanced).toHaveBeenCalledTimes(1);

    rerender(<SettingsNavigation {...baseProps} advancedVisible />);
    fireEvent.click(screen.getByTestId('settings-tab-sso'));
    expect(baseProps.onSelectTab).toHaveBeenCalledWith('sso');
  });

  it('gives navigation actions mobile-friendly 44px touch targets', () => {
    render(<SettingsNavigation {...baseProps} advancedVisible />);

    expect(screen.getByTestId('settings-tab-general')).toHaveClass('min-h-11');
    expect(screen.getByTestId('settings-tab-sso')).toHaveClass('min-h-11');
    expect(screen.getByTestId('settings-advanced-toggle')).toHaveClass('min-h-11');
    expect(screen.getByTestId('settings-tab-general')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('settings-tab-sso')).toHaveAttribute('aria-pressed', 'false');
  });
});
