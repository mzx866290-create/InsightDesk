import { describe, expect, it, vi } from 'vitest'

import { DEFAULT_SSO_FORM } from './ssoSettingsModel'
import { buildGeneralSettingsControllerProps } from './generalSettingsControllerModel'
import type { AdminTokenSettingsController } from './useAdminTokenSettings'
import type { TavilySettingsController } from './useTavilySettings'

describe('generalSettingsControllerModel', () => {
  it('separates daily settings from the low-frequency SSO panel props', () => {
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

    const controller = buildGeneralSettingsControllerProps({
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

    expect(controller.generalSettings).toMatchObject({
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
    expect(controller.ssoSettings).toMatchObject({
      config: null,
      form: DEFAULT_SSO_FORM,
      loading: false,
      saving: false,
      loginStarting: false,
      error: null,
    })
    expect(controller.generalSettings.onLanguageChange).toBe(onLanguageChange)
    expect(controller.generalSettings.onAdminTokenChange).toBe(adminTokenSettings.setAdminToken)
    expect(controller.generalSettings.onSaveAdminToken).toBe(adminTokenSettings.saveAdminToken)
    expect(controller.generalSettings.onClearAdminToken).toBe(adminTokenSettings.clearAdminToken)
    expect(controller.generalSettings.onTavilyKeyChange).toBe(tavilySettings.setTavilyKey)
    expect(controller.generalSettings.onSaveGeneral).toBe(onSaveGeneral)
    expect(controller.generalSettings.onClearTavilyKey).toBe(onClearTavilyKey)
    expect(controller.generalSettings.onResetAgents).toBe(onResetAgents)
    expect(controller.ssoSettings.onFormChange).toBe(ssoSettings.updateForm)
    expect(controller.ssoSettings.onSave).toBe(ssoSettings.save)
    expect(controller.ssoSettings.onStartLogin).toBe(ssoSettings.startLogin)
    expect(controller.ssoSettings.onRefresh).toBe(ssoSettings.load)
  })
})
