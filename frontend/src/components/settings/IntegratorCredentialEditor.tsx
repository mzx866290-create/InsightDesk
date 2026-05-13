import React from 'react'

import {
  CREDENTIAL_TEMPLATES,
  credentialFieldDefinition,
  credentialTemplateById,
  type CredentialFormValues,
  type CredentialInputKey,
  type CredentialMode,
} from './integratorCredentialsModel'

export interface IntegratorCredentialEditorProps {
  credentialMode: CredentialMode
  credentialTemplateId: string
  credentialFormValues: CredentialFormValues
  credentialPatchJson: string
  onCredentialModeChange: (mode: CredentialMode) => void
  onCredentialTemplateChange: (templateId: string) => void
  onCredentialFieldChange: (field: CredentialInputKey, value: string) => void
  onCredentialPatchJsonChange: (value: string) => void
}

export const IntegratorCredentialEditor: React.FC<IntegratorCredentialEditorProps> = ({
  credentialMode,
  credentialTemplateId,
  credentialFormValues,
  credentialPatchJson,
  onCredentialModeChange,
  onCredentialTemplateChange,
  onCredentialFieldChange,
  onCredentialPatchJsonChange,
}) => {
  const selectedCredentialTemplate = credentialTemplateById(credentialTemplateId)

  return (
    <>
      <div className="flex w-full max-w-sm rounded-lg border border-bg-border bg-bg-secondary/40 p-1">
        {(['fields', 'json'] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            className={`h-8 flex-1 rounded-md px-3 text-xs transition-colors ${
              credentialMode === mode
                ? 'bg-accent-blue/20 text-text-primary'
                : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
            }`}
            aria-pressed={credentialMode === mode}
            onClick={() => onCredentialModeChange(mode)}
            data-testid={`settings-integrator-credential-mode-${mode}`}
          >
            {mode === 'fields' ? 'Fields' : 'JSON patch'}
          </button>
        ))}
      </div>

      {credentialMode === 'fields' ? (
        <div className="space-y-3">
          <div className="space-y-2">
            <span className="text-xs font-medium text-text-secondary">Quick template</span>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {CREDENTIAL_TEMPLATES.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  className={`min-h-[4.75rem] rounded-lg border px-3 py-2 text-left transition-colors ${
                    credentialTemplateId === template.id
                      ? 'border-accent-blue/50 bg-accent-blue/10'
                      : 'border-bg-border bg-bg-secondary/30 hover:border-accent-blue/30'
                  }`}
                  onClick={() => onCredentialTemplateChange(template.id)}
                  data-testid={`settings-integrator-credential-template-${template.id}`}
                >
                  <span className="block text-xs font-medium text-text-primary">{template.label}</span>
                  <span className="mt-1 block text-[11px] leading-4 text-text-secondary">
                    {template.description}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {selectedCredentialTemplate.fields.map((field) => {
              const definition = credentialFieldDefinition(field)
              return (
                <label key={field} className="space-y-1 text-xs text-text-secondary">
                  {definition.label}
                  <input
                    type={definition.sensitive ? 'password' : 'text'}
                    className="input-base h-9 w-full"
                    value={credentialFormValues[field]}
                    onChange={(event) => onCredentialFieldChange(field, event.target.value)}
                    placeholder={definition.placeholder}
                    autoComplete="off"
                    data-testid={`settings-integrator-credential-field-${field}`}
                  />
                </label>
              )
            })}
          </div>

          <p className="text-[11px] text-text-secondary">
            Existing credential values are never prefilled. Submitted fields are cleared after rotation.
          </p>
        </div>
      ) : (
        <label className="space-y-1 text-xs text-text-secondary">
          Credential patch JSON
          <textarea
            className="input-base min-h-[7rem] w-full resize-y font-mono text-xs leading-5"
            value={credentialPatchJson}
            onChange={(event) => onCredentialPatchJsonChange(event.target.value)}
            spellCheck={false}
            data-testid="settings-integrator-credential-patch-json"
          />
        </label>
      )}
    </>
  )
}
