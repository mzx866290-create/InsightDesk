import { describe, expect, it, vi } from 'vitest'

import { DEFAULT_SSO_FORM } from './ssoSettingsModel'
import { buildGeneralSettingsPanelProps } from './generalSettingsControllerModel'
import type { AdminTokenSettingsController } from './useAdminTokenSettings'
import type { TavilySettingsController } from './useTavilySettings'

describe('generalSettingsControllerModel', () => {
  it('maps controller slices to GeneralSettingsPanel props without changing the public API', () => {
    const adminTokenSettings = {
      adminToken: 'token',
      adminTokenSaved: true,
      authStatusText: 'admin local',
      setAdminToken: vi.fn(),
      saveAdminToken: vi.fn(),
      clearAdminToken: vi.fn(),
    } satisfies AdminTokenSettingsController
    const ssoSettings = {
      config: null,
      form: DEFAULT_SSO_FORM,
      loading: false,
      saving: false,
      loginStarting: false,
      error: null,
      load: vi.fn(),
      updateForm: vi.fn(),
      save: vi.fn(),
      startLogin: vi.fn(),
    }
    const tavilySettings = {
      tavilyKey: 'tvly-test',
      tavilyKeySet: true,
      saving: false,
      saveOk: true,
      saveError: null,
      setTavilyKey: vi.fn(),
      setTavilyKeySet: vi.fn(),
      setSaveError: vi.fn(),
      saveTavilyKey: vi.fn(),
      clearTavilyKey: vi.fn(),
    } satisfies TavilySettingsController
    const onLanguageChange = vi.fn()
    const onSaveGeneral = vi.fn()
    const onClearTavilyKey = vi.fn()
    const onResetAgents = vi.fn()

    const props = buildGeneralSettingsPanelProps({
      language: 'en-US',
      adminTokenSettings,
      adminAccessError: 'forbidden',
      resetting: true,
      ssoSettings,
      tavilySettings,
      onLanguageChange,
      onSaveGeneral,
      onClearTavilyKey,
      onResetAgents,
    })

    expect(props).toMatchObject({
      language: 'en-US',
      adminToken: 'token',
      adminTokenSaved: true,
      adminAccessError: 'forbidden',
      authStatusText: 'admin local',
      tavilyKey: 'tvly-test',
      tavilyKeySet: true,
      saving: false,
      saveOk: true,
      saveError: null,
      resetting: true,
    })
    expect(props.ssoSettings).toMatchObject({
      config: null,
      form: DEFAULT_SSO_FORM,
      loading: false,
      saving: false,
      loginStarting: false,
      error: null,
    })
    expect(props.onLanguageChange).toBe(onLanguageChange)
    expect(props.onAdminTokenChange).toBe(adminTokenSettings.setAdminToken)
    expect(props.onSaveAdminToken).toBe(adminTokenSettings.saveAdminToken)
    expect(props.onClearAdminToken).toBe(adminTokenSettings.clearAdminToken)
    expect(props.onTavilyKeyChange).toBe(tavilySettings.setTavilyKey)
    expect(props.onSaveGeneral).toBe(onSaveGeneral)
    expect(props.onClearTavilyKey).toBe(onClearTavilyKey)
    expect(props.onResetAgents).toBe(onResetAgents)
    expect(props.ssoSettings.onFormChange).toBe(ssoSettings.updateForm)
    expect(props.ssoSettings.onSave).toBe(ssoSettings.save)
    expect(props.ssoSettings.onStartLogin).toBe(ssoSettings.startLogin)
    expect(props.ssoSettings.onRefresh).toBe(ssoSettings.load)
  })
})
