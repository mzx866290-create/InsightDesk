import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ChatFile, ChatImage } from '../../api/client'
import { ComposerAttachmentTray } from './ComposerAttachmentTray'

const image: ChatImage = {
  name: 'chart.png',
  media_type: 'image/png',
  data_url: 'data:image/png;base64,abc',
}

const file: ChatFile = {
  name: 'notes.pdf',
  media_type: 'application/pdf',
  data_url: 'data:application/pdf;base64,abc',
  size_bytes: 1536,
}

describe('ComposerAttachmentTray', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders image and file attachments with remove actions', () => {
    const onRemoveImage = vi.fn()
    const onRemoveFile = vi.fn()

    render(
      <ComposerAttachmentTray
        images={[image]}
        files={[file]}
        disabled={false}
        onRemoveImage={onRemoveImage}
        onRemoveFile={onRemoveFile}
      />,
    )

    expect(screen.getByAltText('chart.png')).toBeInTheDocument()
    expect(screen.getByText('notes.pdf')).toBeInTheDocument()
    expect(screen.getByText('1.5 KB')).toBeInTheDocument()

    fireEvent.click(screen.getByTitle('Remove image'))
    fireEvent.click(screen.getByTitle('Remove file'))

    expect(onRemoveImage).toHaveBeenCalledWith(0)
    expect(onRemoveFile).toHaveBeenCalledWith(0)
  })

  it('disables remove actions while the composer is locked', () => {
    render(
      <ComposerAttachmentTray
        images={[image]}
        files={[file]}
        disabled
        onRemoveImage={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    )

    expect(screen.getByTitle('Remove image')).toBeDisabled()
    expect(screen.getByTitle('Remove file')).toBeDisabled()
  })

  it('renders nothing when no attachments are present', () => {
    const { container } = render(
      <ComposerAttachmentTray
        images={[]}
        files={[]}
        disabled={false}
        onRemoveImage={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
