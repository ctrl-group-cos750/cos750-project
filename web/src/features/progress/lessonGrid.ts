/**
 * The grid of a lesson page with the progress panel beside it (#214), from 64rem (Tailwind's lg).
 *
 * The lesson and the panel are one group, centred, with the panel right beside the lesson: the
 * lesson's column is as wide as its reading width (48rem, `max-w-3xl`), so a wide screen has no
 * gap between them (1440 and 1920 px). A segment laid out in two columns, or with its picture
 * beside the text, may be wider (up to 100rem), so with one of those on the page the lesson's
 * column takes the rest of the width as before. Minimised, the panel is a 3rem rail; switched
 * off, there is no second column. The classes are written out in full for Tailwind to find.
 */
export function lessonGrid(panelOn: boolean, rail: boolean, widens = true): string {
  if (!panelOn) return ''
  // The activity page's column never widens: always the reading width.
  if (!widens)
    return rail
      ? 'lg:justify-center lg:grid-cols-[minmax(0,48rem)_3rem]'
      : 'lg:justify-center lg:grid-cols-[minmax(0,48rem)_19rem]'
  return rail
    ? 'lg:justify-center lg:grid-cols-[minmax(0,48rem)_3rem] lg:has-[[data-two-column]]:grid-cols-[minmax(0,1fr)_3rem] lg:has-[[data-picture-beside]]:grid-cols-[minmax(0,1fr)_3rem]'
    : 'lg:justify-center lg:grid-cols-[minmax(0,48rem)_19rem] lg:has-[[data-two-column]]:grid-cols-[minmax(0,1fr)_19rem] lg:has-[[data-picture-beside]]:grid-cols-[minmax(0,1fr)_19rem]'
}
