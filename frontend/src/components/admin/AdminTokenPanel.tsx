import React from 'react';

import { useI18n } from '../../i18n';
import { Button } from '../ui/Button';

interface AdminTokenPanelProps {
  token: string;
  saved: boolean;
  error?: string | null;
  description: string;
  onTokenChange: (value: string) => void;
  onSave: () => void;
  onClear: () => void;
  title?: string;
  placeholder?: string;
  statusText?: string | null;
}

export const AdminTokenPanel: React.FC<AdminTokenPanelProps> = ({
  token,
  saved,
  error,
  description,
  onTokenChange,
  onSave,
  onClear,
  title = 'Remote API Token',
  placeholder = 'Enter API token',
  statusText = null,
}) => {
  const { t } = useI18n();
  const configured = token.trim().length > 0;

  return (
    <div
      className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4"
      data-testid="admin-token-panel"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
          <p className="mt-1 text-xs leading-5 text-text-secondary">{description}</p>
        </div>
        <span
          className={`rounded-full px-2 py-1 text-[11px] ${
            configured
              ? 'bg-accent-green/10 text-accent-green'
              : 'bg-bg-secondary text-text-secondary'
          }`}
        >
          {configured ? t('settings.adminToken.configured') : t('settings.adminToken.notSet')}
        </span>
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <input
          data-testid="admin-token-input"
          className="input-base min-h-11 min-w-0 flex-1 text-sm"
          type="password"
          placeholder={placeholder}
          value={token}
          onChange={(e) => onTokenChange(e.target.value)}
        />
        <Button
          data-testid="admin-token-save"
          variant="primary"
          className="min-h-11 justify-center"
          onClick={onSave}
        >
          {saved ? t('settings.adminToken.saved') : t('settings.adminToken.save')}
        </Button>
        <Button
          data-testid="admin-token-clear"
          variant="ghost"
          className="min-h-11 justify-center"
          onClick={onClear}
        >
          {t('settings.adminToken.clear')}
        </Button>
      </div>

      <div className="mt-2 space-y-1">
        <p className="text-[11px] text-text-secondary">{t('settings.adminToken.storageHint')}</p>
        {statusText && (
          <p className="text-[11px] text-accent-blue" data-testid="admin-token-identity">
            {t('settings.adminToken.currentIdentity')}：{statusText}
          </p>
        )}
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}
    </div>
  );
};
