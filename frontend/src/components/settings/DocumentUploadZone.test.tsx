import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DocumentUploadZone } from './DocumentUploadZone'

const file = (name: string): File => new File(['content'], name, { type: 'text/plain' })

describe('DocumentUploadZone', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards selected files to the upload callback and clears the input', () => {
    const onUpload = vi.fn()
    render(<DocumentUploadZone uploading={false} onUpload={onUpload} />)

    const input = screen.getByTestId('settings-documents-upload-input') as HTMLInputElement
    fireEvent.change(input, {
      target: {
        files: [file('intro.md')],
      },
    })

    expect(onUpload).toHaveBeenCalledTimes(1)
    expect(onUpload.mock.calls[0][0]?.[0]?.name).toBe('intro.md')
    expect(input.value).toBe('')
  })

  it('forwards dropped files and resets the drag-over state', () => {
    const onUpload = vi.fn()
    render(<DocumentUploadZone uploading={false} onUpload={onUpload} />)

    const zone = screen.getByTestId('settings-documents-upload-zone')
    fireEvent.dragOver(zone, {
      dataTransfer: {
        files: [file('dropped.txt')],
      },
    })

    expect(zone.className).toContain('border-accent-blue')

    fireEvent.drop(zone, {
      dataTransfer: {
        files: [file('dropped.txt')],
      },
    })

    expect(onUpload).toHaveBeenCalledTimes(1)
    expect(onUpload.mock.calls[0][0]?.[0]?.name).toBe('dropped.txt')
    expect(zone.className).not.toContain('border-accent-blue bg-accent-blue/5')
  })

  it('renders the uploading state', () => {
    render(<DocumentUploadZone uploading={true} onUpload={vi.fn()} />)

    expect(screen.getByText('上传中...')).toBeInTheDocument()
  })
})
