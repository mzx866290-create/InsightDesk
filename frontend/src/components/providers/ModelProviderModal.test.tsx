import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProviderDisplayItem } from './modelProviderModel'
import { useModelProviderController } from './useModelProviderController'
import { ModelProviderModal } from './ModelProviderModal'

vi.mock('../../i18n', () => ({
  useI18n: () => ({
    t: (key: string) =>
      ({
        'modelProviders.title': 'Model Providers',
        'modelProviders.close': 'Close model provider manager',
        'modelProviders.backToList': 'Back to providers',
        'modelProviders.catalogLoading': 'Loading provider catalog...',
        'modelProviders.catalogLoadError': 'Unable to load the provider catalog.',
        'modelProviders.catalogEmpty': 'No providers available',
        'modelProviders.catalogEmptyHint': 'Add a custom provider.',
        'modelProviders.retry': 'Retry',
        'modelProviders.addProvider': 'Add provider',
        'modelProviders.providerName': 'Provider name',
        'modelProviders.baseUrl': 'Base URL',
        'modelProviders.save': 'Save',
        'modelProviders.cancel': 'Cancel',
        'modelProviders.apiKeyClearing': 'Clearing...',
        'modelProviders.apiKeySaved': 'API key saved.',
        'modelProviders.apiKeyCleared': 'API key cleared.',
        'modelProviders.apiKeySaveError': 'Unable to save the API key.',
        'modelProviders.apiKeyClearError': 'Unable to clear the API key.',
        'modelProviders.apiKey': 'API key',
        'modelProviders.apiKeyPlaceholder': 'sk-...',
        'modelProviders.getApiKey': 'Get API key',
        'modelProviders.showApiKey': 'Show API key',
        'modelProviders.hideApiKey': 'Hide API key',
        'modelProviders.enabled': 'Enabled',
        'modelProviders.disabled': 'Disabled',
        'modelProviders.modelList': 'Model list',
        'modelProviders.manageModels': 'Manage models',
        'modelProviders.manageModelsComingSoon': 'Model management coming soon',
        'modelProviders.healthCheck': 'Health check',
        'modelProviders.healthChecking': 'Checking...',
        'modelProviders.healthOk': 'Connection check succeeded.',
        'modelProviders.healthFailed': 'Connection check failed.',
        'modelProviders.noModels': 'No models',
        'modelProviders.noModelsHint': 'Configure a model first',
        'modelProviders.deleteProvider': 'Delete provider',
        'modelProviders.deleteConfirm': 'Delete this provider?',
        'modelProviders.deleteConfirmHint': 'The provider configuration and managed key will be deleted.',
        'modelProviders.deleteError': 'Delete failed. The provider configuration was kept.',
        'modelProviders.deletingProvider': 'Deleting...',
        'modelProviders.keepProvider': 'Keep provider',
        'modelProviders.confirmDelete': 'Confirm delete',
        'settings.cloud.clearKey': 'Clear key',
      })[key] ?? key,
  }),
}))

vi.mock('./useModelProviderController', () => ({
  useModelProviderController: vi.fn(),
}))

const provider: ProviderDisplayItem = {
  id: 'builtin:openai_compatible',
  name: 'OpenAI GPT',
  slug: 'openai_compatible',
  connectionType: 'openai_compatible',
  isBuiltin: true,
  enabled: true,
  apiKeyRef: '',
  baseUrl: 'https://api.openai.com',
  apiKeyUrl: 'https://platform.openai.com/api-keys',
  icon: '🤖',
}

function createController(
  overrides: Partial<ReturnType<typeof useModelProviderController>> = {},
): ReturnType<typeof useModelProviderController> {
  return {
    displayList: [provider],
    selected: provider,
    selectedId: provider.id,
    setSelectedId: vi.fn(),
    apiKeyDraft: 'sk-test',
    setApiKeyDraft: vi.fn(),
    apiKeySaving: false,
    apiKeyClearing: false,
    apiKeyFeedback: null,
    showApiKey: false,
    setShowApiKey: vi.fn(),
    toggleEnabled: vi.fn(),
    saveApiKey: vi.fn(),
    clearApiKey: vi.fn(),
    addingCustom: false,
    setAddingCustom: vi.fn(),
    customName: '',
    setCustomName: vi.fn(),
    customBaseUrl: '',
    setCustomBaseUrl: vi.fn(),
    addCustomProvider: vi.fn(),
    deleteSelected: vi.fn().mockResolvedValue(undefined),
    healthChecking: false,
    healthResult: null,
    runHealthCheck: vi.fn(),
    catalogStatus: 'ready' as const,
    reloadCatalog: vi.fn(),
    catalogLoaded: true,
    ...overrides,
  }
}

describe('ModelProviderModal', () => {
  beforeEach(() => {
    vi.mocked(useModelProviderController).mockReturnValue(createController())
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    document.body.style.overflow = ''
  })

  it('uses the shared dialog and switches from the mobile list pane to detail and back', () => {
    const controller = createController()
    vi.mocked(useModelProviderController).mockReturnValue(controller)

    render(<ModelProviderModal open onClose={vi.fn()} />)

    expect(screen.getByRole('dialog', { name: 'Model Providers' })).toHaveAttribute(
      'aria-modal',
      'true',
    )

    const listPane = screen.getByTestId('model-provider-list-pane')
    const detailPane = screen.getByTestId('model-provider-detail-pane')
    expect(listPane).toHaveClass('flex', 'md:flex', 'md:w-60')
    expect(detailPane).toHaveClass('hidden', 'md:flex', 'min-w-0')

    fireEvent.click(screen.getByRole('button', { name: /OpenAI GPT/ }))

    expect(controller.setSelectedId).toHaveBeenCalledWith(provider.id)
    expect(listPane).toHaveClass('hidden', 'md:flex')
    expect(detailPane).toHaveClass('flex', 'md:flex')

    fireEvent.click(screen.getByRole('button', { name: 'Back to providers' }))

    expect(listPane).toHaveClass('flex', 'md:flex')
    expect(detailPane).toHaveClass('hidden', 'md:flex')
  })

  it('stacks API key controls on narrow screens and keeps desktop actions inline', () => {
    render(<ModelProviderModal open onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /OpenAI GPT/ }))

    const apiKeyInput = screen.getByPlaceholderText('sk-...')
    const apiKeyActions = apiKeyInput.parentElement?.parentElement
    const saveButton = screen.getByRole('button', { name: 'Save' })

    expect(apiKeyActions).toHaveClass('flex-col', 'sm:flex-row')
    expect(saveButton).toHaveClass('w-full', 'sm:w-auto')
  })

  it('distinguishes catalog loading, failure, and empty states with a retry action', () => {
    const loadingController = createController({
      displayList: [],
      selected: null,
      selectedId: null,
      catalogStatus: 'loading',
      catalogLoaded: false,
    })
    vi.mocked(useModelProviderController).mockReturnValue(loadingController)
    const { rerender } = render(<ModelProviderModal open onClose={vi.fn()} />)

    expect(screen.getByRole('status')).toHaveTextContent('Loading provider catalog...')

    const errorController = createController({
      displayList: [],
      selected: null,
      selectedId: null,
      catalogStatus: 'error',
    })
    vi.mocked(useModelProviderController).mockReturnValue(errorController)
    rerender(<ModelProviderModal open onClose={vi.fn()} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Unable to load the provider catalog.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(errorController.reloadCatalog).toHaveBeenCalledTimes(1)

    vi.mocked(useModelProviderController).mockReturnValue(createController({
      displayList: [],
      selected: null,
      selectedId: null,
      catalogStatus: 'ready',
    }))
    rerender(<ModelProviderModal open onClose={vi.fn()} />)

    expect(screen.getByRole('status')).toHaveTextContent('No providers available')
  })

  it('shows real API key links, non-interactive model management, and accessible operation feedback', () => {
    const controller = createController({
      apiKeyFeedback: 'saved',
      healthResult: 'ok',
    })
    vi.mocked(useModelProviderController).mockReturnValue(controller)
    const { rerender } = render(<ModelProviderModal open onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /OpenAI GPT/ }))

    expect(screen.getByRole('link', { name: /Get API key/ })).toHaveAttribute(
      'href',
      'https://platform.openai.com/api-keys',
    )
    expect(screen.getByLabelText(/^API key$/i)).toHaveAttribute('type', 'password')
    fireEvent.click(screen.getByRole('button', { name: 'Show API key' }))
    expect(controller.setShowApiKey).toHaveBeenCalledWith(true)
    expect(screen.getByText('Model management coming soon')).toHaveAttribute(
      'aria-disabled',
      'true',
    )
    expect(screen.queryByRole('button', { name: /Manage models/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole('status').map((item) => item.textContent)).toEqual(
      expect.arrayContaining(['API key saved.', 'Connection check succeeded.']),
    )

    vi.mocked(useModelProviderController).mockReturnValue(createController({
      apiKeyFeedback: 'save_error',
      healthResult: 'fail',
    }))
    rerender(<ModelProviderModal open onClose={vi.fn()} />)

    expect(screen.getAllByRole('alert').map((item) => item.textContent)).toEqual(
      expect.arrayContaining(['Unable to save the API key.', 'Connection check failed.']),
    )
  })

  it('keeps the confirmation open and shows an error when custom provider deletion fails', async () => {
    const customProvider: ProviderDisplayItem = {
      ...provider,
      id: 'custom-provider',
      name: 'Custom Provider',
      isBuiltin: false,
      apiKeyRef: 'managed-custom-key',
      apiKeyUrl: '',
    }
    const deleteSelected = vi
      .fn()
      .mockRejectedValueOnce(new Error('managed key delete failed'))
      .mockResolvedValueOnce(undefined)
    const controller = createController({
      displayList: [customProvider],
      selected: customProvider,
      selectedId: customProvider.id,
      apiKeyDraft: '',
      deleteSelected,
    })
    vi.mocked(useModelProviderController).mockReturnValue(controller)
    render(<ModelProviderModal open onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Custom Provider/ }))

    expect(screen.queryByRole('link', { name: /Get API key/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete provider' }))

    expect(controller.deleteSelected).not.toHaveBeenCalled()
    expect(screen.getByRole('group', { name: 'Delete this provider?' })).toHaveTextContent(
      'The provider configuration and managed key will be deleted.',
    )

    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Delete failed. The provider configuration was kept.',
      )
    })
    expect(screen.getByRole('group', { name: 'Delete this provider?' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))
    await waitFor(() => {
      expect(screen.queryByRole('group', { name: 'Delete this provider?' })).not.toBeInTheDocument()
    })
    expect(controller.deleteSelected).toHaveBeenCalledTimes(2)
  })
})
