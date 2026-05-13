import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { KbUploadFileList } from './KbUploadFileList'

const file = (name: string, size: number): File => (
  new File(['a'.repeat(size)], name, { type: 'text/plain' })
)

describe('KbUploadFileList', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing when there are no files', () => {
    const { container } = render(<KbUploadFileList files={[]} onRemoveFile={vi.fn()} />)

    expect(container.firstChild).toBeNull()
  })

  it('renders selected file names and sizes', () => {
    render(
      <KbUploadFileList
        files={[
          file('intro.md', 2048),
          file('diagram.png', 3072),
        ]}
        onRemoveFile={vi.fn()}
      />,
    )

    expect(screen.getByText('intro.md')).toBeInTheDocument()
    expect(screen.getByText('diagram.png')).toBeInTheDocument()
    expect(screen.getByText('2 KB')).toBeInTheDocument()
    expect(screen.getByText('3 KB')).toBeInTheDocument()
  })

  it('forwards the removed file name', () => {
    const onRemoveFile = vi.fn()

    render(
      <KbUploadFileList
        files={[
          file('intro.md', 2048),
          file('diagram.png', 3072),
        ]}
        onRemoveFile={onRemoveFile}
      />,
    )

    const row = screen.getByText('diagram.png').closest('div')
    expect(row).not.toBeNull()
    fireEvent.click(within(row as HTMLElement).getByRole('button'))

    expect(onRemoveFile).toHaveBeenCalledWith('diagram.png')
  })
})
