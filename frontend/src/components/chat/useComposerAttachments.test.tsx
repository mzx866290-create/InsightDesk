import { act, cleanup, renderHook } from '@testing-library/react'
import type { ChangeEvent, ClipboardEvent } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ChatImage } from '../../api/client'
import { MAX_IMAGE_COUNT, MAX_IMAGE_FILE_SIZE_BYTES } from './messageInputUtils'
import { useComposerAttachments } from './useComposerAttachments'

const image = (index: number): ChatImage => ({
  name: `image-${index}.png`,
  media_type: 'image/png',
  data_url: `data:image/png;base64,${['YQ==', 'Yg==', 'Yw==', 'ZA==', 'ZQ=='][index] ?? 'Zg=='}`,
})

describe('useComposerAttachments image guards', () => {
  beforeEach(() => {
    vi.spyOn(window, 'alert').mockImplementation(() => undefined)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('rejects an oversized image selected from the file picker before reading it', async () => {
    const { result } = renderHook(() => useComposerAttachments())
    const file = new File(['x'], 'large.png', { type: 'image/png' })
    Object.defineProperty(file, 'size', { value: MAX_IMAGE_FILE_SIZE_BYTES + 1 })
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [file] })

    await act(async () => {
      await result.current.handleSelectImages({ target: input } as ChangeEvent<HTMLInputElement>)
    })

    expect(result.current.images).toEqual([])
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('单张最大 10 MB'))
  })

  it('rejects pasted images when the combined count would exceed the limit', async () => {
    const { result } = renderHook(() => useComposerAttachments())
    act(() => {
      result.current.mergeAttachments(
        Array.from({ length: MAX_IMAGE_COUNT }, (_, index) => image(index)),
        [],
      )
    })

    const pastedFile = new File(['x'], 'pasted.png', { type: 'image/png' })
    const preventDefault = vi.fn()
    const event = {
      clipboardData: {
        items: [
          {
            getAsFile: () => pastedFile,
            kind: 'file',
            type: 'image/png',
          },
        ],
      },
      preventDefault,
    } as unknown as ClipboardEvent<HTMLTextAreaElement>

    await act(async () => {
      await result.current.handlePaste(event)
    })

    expect(preventDefault).toHaveBeenCalledTimes(1)
    expect(result.current.images).toHaveLength(MAX_IMAGE_COUNT)
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('最多只能附加 4 张图片'))
  })

  it('applies the same count limit to externally merged composer attachments', () => {
    const { result } = renderHook(() => useComposerAttachments())

    act(() => {
      result.current.mergeAttachments(
        Array.from({ length: MAX_IMAGE_COUNT + 1 }, (_, index) => image(index)),
        [],
      )
    })

    expect(result.current.images).toEqual([])
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('最多只能附加 4 张图片'))
  })

  it('does not restore malformed image data after a failed send', () => {
    const { result } = renderHook(() => useComposerAttachments())

    act(() => {
      result.current.restoreAttachments(
        [{ name: 'broken.png', media_type: 'image/png', data_url: 'not-a-data-url' }],
        [],
      )
    })

    expect(result.current.images).toEqual([])
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('无效或已损坏'))
  })
})
