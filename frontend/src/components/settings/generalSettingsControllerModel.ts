import type { AppLanguage } from '../../stores/chatStore'
import type { SsoConfig } from '../../api/client'
import type { GeneralSettingsPanelProps } from './GeneralSettingsPanel'
import type { SsoConfigForm } from './ssoSettingsModel'
import type { AdminTokenSettingsController } from './useAdminTokenSettings'
import type { TavilySettingsController } from './useTavilySettings'

interface SsoSettingsController {
  config: SsoConfig | null
  form: SsoConfigForm
  loading: boolean
  saving: boolean
  loginStarting: boolean
  error: string | null
  load: () => Promise<void>
  updateForm: <Key extends keyof SsoConfigForm>(key: Key, value: SsoConfigForm[Key]) => void
  save: () => Promise<void>
  startLogin: () => Promise<void>
}

interface BuildGeneralSettingsPanelPropsOptions {
  adminAccessError: string | null
  adminTokenSettings: AdminTokenSettingsController
  language: AppLanguage
  resetting: boolean
  ssoSettings: SsoSettingsController
  tavilySettings: TavilySettingsController
  onLanguageChange: (language: AppLanguage) => void
  onResetAgents: () => void
  onSaveGeneral: () => void
  onClearTavilyKey: () => void
}

export function buildGeneralSettingsPanelProps({
  adminAccessError,
  adminTokenSettings,
  language,
  resetting,
  ssoSettings,
  tavilySettings,
  onLanguageChange,
  onResetAgents,
  onSaveGeneral,
  onClearTavilyKey,
}: BuildGeneralSettingsPanelPropsOptions): GeneralSettingsPanelProps {
  return {
    language,
    adminToken: adminTokenSettings.adminToken,
    adminTokenSaved: adminTokenSettings.adminTokenSaved,
    adminAccessError,
    authStatusText: adminTokenSettings.authStatusText,
    tavilyKey: tavilySettings.tavilyKey,
    tavilyKeySet: tavilySettings.tavilyKeySet,
    saving: tavilySettings.saving,
    saveOk: tavilySettings.saveOk,
    saveError: tavilySettings.saveError,
    resetting,
    ssoSettings: {
      config: ssoSettings.config,
      form: ssoSettings.form,
      loading: ssoSettings.loading,
      saving: ssoSettings.saving,
      loginStarting: ssoSettings.loginStarting,
      error: ssoSettings.error,
      onFormChange: ssoSettings.updateForm,
      onSave: ssoSettings.save,
      onStartLogin: ssoSettings.startLogin,
      onRefresh: ssoSettings.load,
    },
    onLanguageChange,
    onAdminTokenChange: adminTokenSettings.setAdminToken,
    onSaveAdminToken: adminTokenSettings.saveAdminToken,
    onClearAdminToken: adminTokenSettings.clearAdminToken,
    onTavilyKeyChange: tavilySettings.setTavilyKey,
    onSaveGeneral,
    onClearTavilyKey,
    onResetAgents,
  }
}
