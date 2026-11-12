import { describe, expect, it } from 'vitest'
import { dataUrlBytes, squarePicture } from './squarePicture.ts'

describe('squarePicture', () => {
  it('counts the bytes a data URL decodes to', () => {
    expect(dataUrlBytes(`data:image/png;base64,${btoa('abc')}`)).toBe(3)
    expect(dataUrlBytes(`data:image/png;base64,${btoa('abcd')}`)).toBe(4)
    expect(dataUrlBytes(`data:image/png;base64,${btoa('abcde')}`)).toBe(5)
  })

  it('refuses a file that is not a picture before reading it', async () => {
    await expect(squarePicture(new File(['x'], 'a.txt', { type: 'text/plain' }))).rejects.toThrow(
      'Choose a picture',
    )
  })
})
