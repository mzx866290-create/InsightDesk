import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { SettingsTabId } from '../../stores/chatStore';

export type SettingsTab = SettingsTabId;

export type SettingsTabItem = [SettingsTab, string];

export interface SettingsNavigationProps {
  activeTab: SettingsTab;
  primaryTabs: SettingsTabItem[];
  advancedTabs: SettingsTabItem[];
  advancedVisible: boolean;
  dailyTitle: string;
  dailyDescription: string;
  advancedTitle: string;
  advancedDescription: string;
  advancedCollapsedHint: string;
  onSelectTab: (tab: SettingsTab) => void;
  onToggleAdvanced: () => void;
}

function SettingsTabButton({
  active,
  item,
  onSelectTab,
}: {
  active: boolean;
  item: SettingsTabItem;
  onSelectTab: (tab: SettingsTab) => void;
}) {
  const [id, label] = item;

  return (
    <button
      key={id}
      type="button"
      onClick={() => onSelectTab(id)}
      data-testid={`settings-tab-${id}`}
      aria-pressed={active}
      className={`min-h-11 min-w-[7rem] flex-1 rounded-md px-3 py-2 text-xs font-medium transition-colors ${
        active
          ? 'bg-bg-secondary text-text-primary shadow-sm'
          : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
      }`}
    >
      {label}
    </button>
  );
}

export const SettingsNavigation: React.FC<SettingsNavigationProps> = ({
  activeTab,
  primaryTabs,
  advancedTabs,
  advancedVisible,
  dailyTitle,
  dailyDescription,
  advancedTitle,
  advancedDescription,
  advancedCollapsedHint,
  onSelectTab,
  onToggleAdvanced,
}) => (
  <div className="mb-5 space-y-3">
    <div className="rounded-lg border border-bg-border bg-bg-tertiary/70 p-2">
      <div className="mb-2 px-1">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
          {dailyTitle}
        </p>
        <p className="mt-0.5 text-[11px] leading-4 text-text-secondary/80">{dailyDescription}</p>
      </div>
      <div className="flex flex-wrap gap-1">
        {primaryTabs.map((item) => (
          <SettingsTabButton
            key={item[0]}
            active={activeTab === item[0]}
            item={item}
            onSelectTab={onSelectTab}
          />
        ))}
      </div>
    </div>

    <div className="rounded-lg border border-bg-border bg-bg-tertiary/40 p-2">
      <button
        type="button"
        onClick={onToggleAdvanced}
        data-testid="settings-advanced-toggle"
        className="flex min-h-11 w-full items-center justify-between gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-bg-hover"
        aria-expanded={advancedVisible}
      >
        <span>
          <span className="block text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
            {advancedTitle}
          </span>
          <span className="mt-0.5 block text-[11px] leading-4 text-text-secondary/80">
            {advancedVisible ? advancedDescription : advancedCollapsedHint}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2 text-[11px] font-medium text-text-secondary">
          {advancedTabs.length}
          {advancedVisible ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </span>
      </button>

      {advancedVisible && (
        <div className="mt-2 flex flex-wrap gap-1 border-t border-bg-border pt-2">
          {advancedTabs.map((item) => (
            <SettingsTabButton
              key={item[0]}
              active={activeTab === item[0]}
              item={item}
              onSelectTab={onSelectTab}
            />
          ))}
        </div>
      )}
    </div>
  </div>
);
