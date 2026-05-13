import { describe, expect, it } from 'vitest'

import type { CloudModelProfile } from '../../stores/chatStoreModel'
import {
  buildCloudModelProfileInput,
  canSaveCloudModelProfileForm,
  cloudModelProfileToForm,
  defaultCloudModelProfileForm,
  findCloudModelProfileById,
  buildCloudModelProfileClearedApiKeyInput,
  normalizedCloudProfileApiKey,
} from './cloudModelProfilesModel'

describe('cloudModelProfilesModel', () => {
  it('returns a fresh default form', () => {
    const first = defaultCloudModelProfileForm()
    const second = defaultCloudModelProfileForm()

    first.name = 'mutated'

    expect(second).toEqual({
      name: '',
      model: 'openai/gpt-4o-mini',
      baseUrl: 'https://openrouter.ai/api/v1',
      apiKey: '',
      temperature: 0.3,
    })
  })

  it('maps an existing profile into an edit form without exposing the API key', () => {
    const profile: CloudModelProfile = {
      id: 'profile-1',
      name: 'Prod OpenRouter',
      modelConfig: {
        panel_id: 'profile-1',
        connection_type: 'openai_compatible',
        provider: 'openai_compatible',
        model: 'openai/gpt-4.1',
        base_url: 'https://openrouter.ai/api/v1',
        api_key: 'should-not-fill',
        api_key_ref: 'secret-ref',
        temperature: 0.7,
        agent_mode: 'auto',
      },
      createdAt: 1,
      updatedAt: 2,
    }

    expect(cloudModelProfileToForm(profile)).toEqual({
      name: 'Prod OpenRouter',
      model: 'openai/gpt-4.1',
      baseUrl: 'https://openrouter.ai/api/v1',
      apiKey: '',
      temperature: 0.7,
    })
  })

  it('validates required fields and normalizes API keys', () => {
    const form = {
      name: '  Prod  ',
      model: ' openai/gpt-4.1 ',
      baseUrl: ' https://api.example.test/v1 ',
      apiKey: ' sk-test ',
      temperature: 0.2,
    }

    expect(canSaveCloudModelProfileForm(form)).toBe(true)
    expect(canSaveCloudModelProfileForm({ ...form, model: '   ' })).toBe(false)
    expect(normalizedCloudProfileApiKey(form)).toBe('sk-test')
  })

  it('builds the persisted cloud model profile payload', () => {
    const payload = buildCloudModelProfileInput(
      {
        name: '  Prod  ',
        model: ' openai/gpt-4.1 ',
        baseUrl: ' https://api.example.test/v1 ',
        apiKey: 'sk-test',
        temperature: 0.4,
      },
      'profile-1',
      'api-key-ref-1',
    )

    expect(payload).toEqual({
      id: 'profile-1',
      name: 'Prod',
      modelConfig: {
        panel_id: 'profile-1',
        connection_type: 'openai_compatible',
        provider: 'openai_compatible',
        model: 'openai/gpt-4.1',
        base_url: 'https://api.example.test/v1',
        api_key: '',
        api_key_ref: 'api-key-ref-1',
        temperature: 0.4,
        agent_mode: 'auto',
      },
    })
  })

  it('finds profiles by id without treating empty ids as matches', () => {
    const profile: CloudModelProfile = {
      id: 'profile-1',
      name: 'Prod',
      modelConfig: {
        panel_id: 'profile-1',
        connection_type: 'openai_compatible',
        provider: 'openai_compatible',
        model: 'openai/gpt-4.1',
        base_url: 'https://api.example.test/v1',
        api_key: '',
        api_key_ref: 'secret-ref',
        temperature: 0.4,
        agent_mode: 'auto',
      },
      createdAt: 1,
      updatedAt: 2,
    }

    expect(findCloudModelProfileById([profile], 'profile-1')).toBe(profile)
    expect(findCloudModelProfileById([profile], null)).toBeNull()
    expect(findCloudModelProfileById([profile], 'missing')).toBeNull()
  })

  it('builds the cleared API key payload while preserving profile config', () => {
    const profile: CloudModelProfile = {
      id: 'profile-1',
      name: 'Prod',
      modelConfig: {
        panel_id: 'profile-1',
        connection_type: 'openai_compatible',
        provider: 'openai_compatible',
        model: 'openai/gpt-4.1',
        base_url: 'https://api.example.test/v1',
        api_key: 'stored-secret',
        api_key_ref: 'secret-ref',
        temperature: 0.4,
        agent_mode: 'auto',
      },
      createdAt: 1,
      updatedAt: 2,
    }

    expect(buildCloudModelProfileClearedApiKeyInput(profile)).toEqual({
      id: 'profile-1',
      name: 'Prod',
      modelConfig: {
        ...profile.modelConfig,
        api_key: '',
        api_key_ref: '',
      },
    })
  })
})
