import type { CloudModelProfile, CloudModelProfileInput } from '../../stores/chatStoreModel'

export interface CloudModelProfileForm {
  name: string
  model: string
  baseUrl: string
  apiKey: string
  temperature: number
}

export const DEFAULT_CLOUD_MODEL_PROFILE_FORM: CloudModelProfileForm = {
  name: '',
  model: 'openai/gpt-4o-mini',
  baseUrl: 'https://openrouter.ai/api/v1',
  apiKey: '',
  temperature: 0.3,
}

export function defaultCloudModelProfileForm(): CloudModelProfileForm {
  return { ...DEFAULT_CLOUD_MODEL_PROFILE_FORM }
}

export function cloudModelProfileToForm(profile: CloudModelProfile): CloudModelProfileForm {
  return {
    name: profile.name,
    model: profile.modelConfig.model,
    baseUrl: profile.modelConfig.base_url,
    apiKey: '',
    temperature: profile.modelConfig.temperature,
  }
}

export function canSaveCloudModelProfileForm(form: CloudModelProfileForm): boolean {
  return Boolean(form.name.trim() && form.model.trim() && form.baseUrl.trim())
}

export function findCloudModelProfileById(
  profiles: CloudModelProfile[],
  profileId: string | null,
): CloudModelProfile | null {
  if (!profileId) {
    return null
  }

  return profiles.find((profile) => profile.id === profileId) ?? null
}

export function normalizedCloudProfileApiKey(form: CloudModelProfileForm): string {
  return form.apiKey.trim()
}

export function buildCloudModelProfileInput(
  form: CloudModelProfileForm,
  editingProfileId: string | null,
  apiKeyRef: string,
): CloudModelProfileInput {
  return {
    id: editingProfileId ?? undefined,
    name: form.name.trim(),
    modelConfig: {
      panel_id: editingProfileId ?? 'cloud-profile-editor',
      connection_type: 'openai_compatible',
      provider: 'openai_compatible',
      model: form.model.trim(),
      base_url: form.baseUrl.trim(),
      api_key: '',
      api_key_ref: apiKeyRef,
      temperature: form.temperature,
      agent_mode: 'auto',
    },
  }
}

export function buildCloudModelProfileClearedApiKeyInput(
  profile: CloudModelProfile,
): CloudModelProfileInput {
  return {
    id: profile.id,
    name: profile.name,
    modelConfig: {
      ...profile.modelConfig,
      api_key: '',
      api_key_ref: '',
    },
  }
}
