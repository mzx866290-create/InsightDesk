import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getDeliveryTemplateCatalog,
  installDeliveryTemplateManifest,
  uninstallDeliveryTemplateManifest,
} from '../../api/client'
import { DeliveryTemplateCatalogPanel } from './DeliveryTemplateCatalogPanel'

vi.mock('../../api/client', () => ({
  getDeliveryTemplateCatalog: vi.fn(),
  installDeliveryTemplateManifest: vi.fn(),
  uninstallDeliveryTemplateManifest: vi.fn(),
}))

describe('DeliveryTemplateCatalogPanel', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders summary, template rows, and refresh action', async () => {
    vi.mocked(getDeliveryTemplateCatalog).mockResolvedValue({
      templates: [
        {
          id: 'executive_report',
          name: 'Executive Report',
          description: 'Decision-ready report.',
          artifact_type: 'report',
          category: 'business',
          tags: ['executive'],
          target_format: 'markdown',
          preview: 'Summary → Actions',
          suggested_options: { tone: 'executive' },
          metadata: { source: 'builtin' },
        },
        {
          id: 'board_deck',
          name: 'Board Deck',
          description: 'Board-ready deck.',
          artifact_type: 'deck',
          category: 'presentation',
          tags: ['pptx'],
          target_format: 'pptx',
          preview: 'Cover → Evidence',
          suggested_options: { target_slide_count: 8 },
          metadata: { manifest: true },
        },
      ],
      summary: { total: 2, builtin: 1, manifest: 1, report: 1, deck: 1 },
      manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 1,
        issue_count: 0,
        issues: [],
      },
    })

    render(<DeliveryTemplateCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-delivery-template-summary')).toBeInTheDocument()
    })
    expect(screen.getByText('Executive Report')).toBeInTheDocument()
    expect(screen.getByText('Board Deck')).toBeInTheDocument()
    expect(screen.getByText('Built-in')).toBeInTheDocument()
    expect(screen.getByText('Manifest')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('settings-delivery-template-refresh'))
    expect(getDeliveryTemplateCatalog).toHaveBeenCalledTimes(2)
  })

  it('shows manifest validation issues', async () => {
    vi.mocked(getDeliveryTemplateCatalog).mockResolvedValue({
      templates: [],
      summary: { total: 0, builtin: 0, manifest: 0, report: 0, deck: 0 },
      manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 0,
        issue_count: 1,
        issues: [
          {
            file: 'config/delivery_templates/bad.json',
            code: 'invalid_manifest',
            message: 'tags cannot be empty',
          },
        ],
      },
    })

    render(<DeliveryTemplateCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-delivery-template-manifest-issues')).toHaveTextContent('invalid_manifest')
    })
    expect(screen.getByText('config/delivery_templates/bad.json')).toBeInTheDocument()
  })

  it('surfaces loader errors', async () => {
    vi.mocked(getDeliveryTemplateCatalog).mockRejectedValue(new Error('template catalog unavailable'))

    render(<DeliveryTemplateCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-delivery-template-error')).toHaveTextContent('template catalog unavailable')
    })
  })

  it('installs and uninstalls delivery template manifests', async () => {
    vi.mocked(getDeliveryTemplateCatalog).mockResolvedValue({
      templates: [],
      summary: { total: 0, builtin: 0, manifest: 0, report: 0, deck: 0 },
      manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 0,
        loaded_count: 0,
        issue_count: 0,
        issues: [],
      },
    })
    vi.mocked(installDeliveryTemplateManifest).mockResolvedValue({
      templates: [
        {
          id: 'sales_readout',
          name: 'Sales Readout',
          description: 'Sales team readout deck.',
          artifact_type: 'deck',
          category: 'sales',
          tags: ['sales', 'deck'],
          target_format: 'pptx',
          preview: 'Pipeline -> Risks',
          suggested_options: { target_slide_count: 6 },
          metadata: { manifest: true, source: 'template_manifest' },
        },
      ],
      summary: { total: 1, builtin: 0, manifest: 1, report: 0, deck: 1 },
      manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 1,
        issue_count: 0,
        issues: [],
      },
      installed: {
        id: 'sales_readout',
        manifest_path: 'config/delivery_templates/sales_readout.json',
        executed_template_code: false,
      },
    })
    vi.mocked(uninstallDeliveryTemplateManifest).mockResolvedValue({
      templates: [],
      summary: { total: 0, builtin: 0, manifest: 0, report: 0, deck: 0 },
      manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 0,
        issue_count: 0,
        issues: [],
      },
      uninstalled: {
        id: 'sales_readout',
        manifest_path: 'config/delivery_templates/sales_readout.json',
        deleted_manifest: true,
        existed: true,
      },
    })

    render(<DeliveryTemplateCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-delivery-template-install-panel')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('settings-delivery-template-install-submit'))

    await waitFor(() => {
      expect(installDeliveryTemplateManifest).toHaveBeenCalled()
    })
    expect(await screen.findByTestId('settings-delivery-template-success')).toHaveTextContent(
      'Installed sales_readout; template code execution: no.',
    )
    expect(screen.getByTestId('settings-delivery-template-uninstall-sales_readout')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('settings-delivery-template-uninstall-sales_readout'))
    await waitFor(() => {
      expect(uninstallDeliveryTemplateManifest).toHaveBeenCalledWith('sales_readout')
    })
    expect(await screen.findByTestId('settings-delivery-template-success')).toHaveTextContent(
      'Uninstalled sales_readout; manifest deleted: yes.',
    )
  })
})
