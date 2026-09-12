import { describe, expect, it } from 'vitest'

import type { ChatImage } from '../../api/client'
import {
  MAX_IMAGE_COUNT,
  MAX_IMAGE_FILE_SIZE_BYTES,
  MAX_IMAGE_TOTAL_SIZE_BYTES,
  mergeImagesWithinLimits,
  validateChatImage,
  validateImageFile,
} from './messageInputUtils'

const image = (
  name: string,
  encoded = 'YQ==',
  mediaType = 'image/png',
  dataUrlMediaType = mediaType,
): ChatImage => ({
  name,
  media_type: mediaType,
  data_url: `data:${dataUrlMediaType};base64,${encoded}`,
})

describe('chat image attachment limits', () => {
  it('uses the documented default count and byte limits', () => {
    expect(MAX_IMAGE_COUNT).toBe(4)
    expect(MAX_IMAGE_FILE_SIZE_BYTES).toBe(10 * 1024 * 1024)
    expect(MAX_IMAGE_TOTAL_SIZE_BYTES).toBe(20 * 1024 * 1024)
  })

  it('validates selected image media types and file sizes before reading', () => {
    const unsupported = new File(['svg'], 'diagram.svg', { type: 'image/svg+xml' })
    expect(validateImageFile(unsupported)).toContain('不支持的图片类型')

    const oversized = new File(['x'], 'large.png', { type: 'image/png' })
    Object.defineProperty(oversized, 'size', { value: MAX_IMAGE_FILE_SIZE_BYTES + 1 })
    expect(validateImageFile(oversized)).toContain('单张最大 10 MB')
  })

  it('validates serialized image data URLs and declared media types', () => {
    expect(validateChatImage(image('valid.png'))).toEqual({ error: null, sizeBytes: 1 })
    expect(validateChatImage(image('mismatch.png', 'YQ==', 'image/png', 'image/jpeg')).error)
      .toContain('媒体类型与 data URL 不一致')
    expect(validateChatImage({
      name: 'broken.png',
      media_type: 'image/png',
      data_url: 'data:image/png;base64,***',
    }).error).toContain('无效或已损坏')
    expect(validateChatImage({
      name: 'raw.png',
      media_type: 'image/png',
      data_url: 'data:image/png,%89PNG',
    }).error).toContain('无效或已损坏')
  })

  it('rejects incoming image batches atomically when count or total size is exceeded', () => {
    const countResult = mergeImagesWithinLimits(
      [],
      [image('1.png', 'YQ=='), image('2.png', 'Yg=='), image('3.png', 'Yw==')],
      { maxBytes: 4, maxCount: 2, maxTotalBytes: 8 },
    )
    expect(countResult.images).toEqual([])
    expect(countResult.error).toContain('最多只能附加 2 张图片')

    const totalResult = mergeImagesWithinLimits(
      [],
      [image('1.png', 'YWI='), image('2.png', 'Y2Q=')],
      { maxBytes: 3, maxCount: 4, maxTotalBytes: 3 },
    )
    expect(totalResult.images).toEqual([])
    expect(totalResult.error).toContain('总大小不能超过')
  })

  it('deduplicates exact images without weakening the limits', () => {
    const first = image('same.png')
    const result = mergeImagesWithinLimits([first], [first])

    expect(result).toEqual({ error: null, images: [first] })
  })
})
