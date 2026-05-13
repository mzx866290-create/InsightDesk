import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  EMPTY_CREDENTIAL_FORM,
  type CredentialFormValues,
} from './integratorCredentialsModel'
import { IntegratorCredentialEditor } from './IntegratorCredentialEditor'

const credentialFormValues: CredentialFormValues = {
  ...EMPTY_CREDENTIAL_FORM,
  token: 'existing-token',
}

describe('IntegratorCredentialEditor', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders fields mode templates and forwards template, field, and mode changes', () => {
    const onCredentialModeChange = vi.fn()
    const onCredentialTemplateChange = vi.fn()
    const onCredentialFieldChange = vi.fn()

    render(
      <IntegratorCredentialEditor
        credentialMode="fields"
        credentialTemplateId="token"
        credentialFormValues={credentialFormValues}
        credentialPatchJson={'{\n  "token": ""\n}'}
        onCredentialModeChange={onCredentialModeChange}
        onCredentialTemplateChange={onCredentialTemplateChange}
        onCredentialFieldChange={onCredentialFieldChange}
        onCredentialPatchJsonChange={vi.fn()}
      />,
    )

    expect(screen.getByText('Quick template')).toBeInTheDocument()
    expect(screen.getByTestId('settings-integrator-credential-template-token')).toHaveTextContent('Token')
    expect(screen.getByTestId('settings-integrator-credential-field-token')).toHaveValue('existing-token')

    fireEvent.click(screen.getByTestId('settings-integrator-credential-template-api_key'))
    expect(onCredentialTemplateChange).toHaveBeenCalledWith('api_key')

    fireEvent.change(screen.getByTestId('settings-integrator-credential-field-token'), {
      target: { value: 'next-token' },
    })
    expect(onCredentialFieldChange).toHaveBeenCalledWith('token', 'next-token')

    fireEvent.click(screen.getByTestId('settings-integrator-credential-mode-json'))
    expect(onCredentialModeChange).toHaveBeenCalledWith('json')
  })

  it('renders json mode and forwards patch edits', () => {
    const onCredentialPatchJsonChange = vi.fn()

    render(
      <IntegratorCredentialEditor
        credentialMode="json"
        credentialTemplateId="token"
        credentialFormValues={credentialFormValues}
        credentialPatchJson={'{\n  "client_secret": ""\n}'}
        onCredentialModeChange={vi.fn()}
        onCredentialTemplateChange={vi.fn()}
        onCredentialFieldChange={vi.fn()}
        onCredentialPatchJsonChange={onCredentialPatchJsonChange}
      />,
    )

    const textarea = screen.getByTestId('settings-integrator-credential-patch-json')
    expect(textarea).toHaveValue('{\n  "client_secret": ""\n}')

    fireEvent.change(textarea, {
      target: { value: '{ "client_secret": "next" }' },
    })

    expect(onCredentialPatchJsonChange).toHaveBeenCalledWith('{ "client_secret": "next" }')
  })
})
