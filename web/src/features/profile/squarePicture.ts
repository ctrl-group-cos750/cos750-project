/** The size an uploaded picture is stored at: sharp at the largest place it shows (72 px on the
 * profile page, on a 3x phone screen), and small enough to stay well under the API's 200 kB. */
export const PICTURE_SIZE = 256
const MAX_BYTES = 200_000

/**
 * Turns the photo a student chose into a small square picture, as a data URL ready for the API.
 * The middle square is kept and scaled to 256 px. Drawing it on a canvas also drops what a phone
 * photo carries (location, camera, date), so none of that leaves the student's device (POPIA).
 * WebP where the browser can make it, else JPEG; quality is lowered until it fits.
 */
export async function squarePicture(file: File): Promise<string> {
  if (!file.type.startsWith('image/')) throw new Error('Choose a picture (a PNG, JPEG or WebP).')
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    throw new Error("This picture can't be opened. Try a PNG, JPEG or WebP.")
  }
  const side = Math.min(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = PICTURE_SIZE
  canvas.height = PICTURE_SIZE
  const context = canvas.getContext('2d')
  if (!context) throw new Error("Your browser can't prepare the picture.")
  context.imageSmoothingQuality = 'high'
  context.drawImage(
    bitmap,
    (bitmap.width - side) / 2,
    (bitmap.height - side) / 2,
    side,
    side,
    0,
    0,
    PICTURE_SIZE,
    PICTURE_SIZE,
  )
  bitmap.close()
  for (const quality of [0.9, 0.8, 0.65, 0.5]) {
    let url = canvas.toDataURL('image/webp', quality)
    // Safari can't make WebP and gives a PNG instead: use JPEG there.
    if (!url.startsWith('data:image/webp')) url = canvas.toDataURL('image/jpeg', quality)
    if (dataUrlBytes(url) <= MAX_BYTES) return url
  }
  throw new Error('The picture is too big. Choose a smaller one.')
}

/** How many bytes the data URL decodes to. */
export function dataUrlBytes(url: string): number {
  const data = url.slice(url.indexOf(',') + 1)
  return Math.floor((data.length * 3) / 4) - (data.endsWith('==') ? 2 : data.endsWith('=') ? 1 : 0)
}
