import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScrollRegion } from './index.ts'

// jsdom does no layout: these stand in for the box's widths and scroll position, and a fake
// ResizeObserver lets a test say "the window was resized".
let widths = { scroll: 900, client: 300, left: 0 }
let resize: () => void = () => {}

beforeEach(() => {
  widths = { scroll: 900, client: 300, left: 0 }
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(() => widths.scroll)
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => widths.client)
  vi.spyOn(HTMLElement.prototype, 'scrollLeft', 'get').mockImplementation(() => widths.left)
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resize = callback
      }
      observe() {}
      disconnect() {}
    },
  )
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function setup() {
  render(
    <>
      <button type="button">Before</button>
      <ScrollRegion label="Table: Step, Queue">
        <table>
          <tbody>
            <tr>
              <td>wide</td>
            </tr>
          </tbody>
        </table>
      </ScrollRegion>
      <button type="button">After</button>
    </>,
  )
  return () => screen.queryByRole('region', { name: 'Table: Step, Queue' })
}

describe('ScrollRegion', () => {
  it('is a named tab stop only while it overflows, and follows resizes', () => {
    const region = setup()
    expect(region()).toHaveAttribute('tabindex', '0')
    widths.scroll = 300
    act(() => resize())
    expect(region()).toBeNull()
    expect(document.querySelector('section')).not.toHaveAttribute('tabindex')
    widths.scroll = 900
    act(() => resize())
    expect(region()).toHaveAttribute('tabindex', '0')
  })

  it('keeps focus when a resize makes it fit while it has focus, then lets go on blur', async () => {
    const region = setup()
    const box = region()!
    act(() => box.focus())
    widths.scroll = 300 // e.g. the window widened from 320 to 1280 px
    act(() => resize())
    expect(box).toHaveFocus() // still focusable, so focus is not dropped on <body>
    expect(box).toHaveAttribute('tabindex', '0')

    act(() => screen.getByRole('button', { name: 'After' }).focus())
    await act(() => new Promise((resolve) => setTimeout(resolve, 5)))
    expect(box).not.toHaveAttribute('tabindex') // re-evaluated once focus left
    expect(screen.getByRole('button', { name: 'After' })).toHaveFocus()
  })

  it('keeps the region while focus is on something inside it, such as a fill-in blank', () => {
    render(
      <ScrollRegion label="Python code with blanks">
        <select aria-label="Blank 1">
          <option>a</option>
        </select>
      </ScrollRegion>,
    )
    const box = screen.getByRole('region', { name: 'Python code with blanks' })
    act(() => screen.getByRole('combobox', { name: 'Blank 1' }).focus())
    widths.scroll = 300
    act(() => resize())
    expect(box).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('combobox', { name: 'Blank 1' })).toHaveFocus()
  })

  it('shows the scroll cue on the edges where content is hidden', () => {
    const region = setup()
    const frame = region()!.parentElement!
    expect(frame).toHaveAttribute('data-more-end')
    expect(frame).not.toHaveAttribute('data-more-start')

    widths.left = 300 // scrolled to the middle
    fireEvent.scroll(region()!)
    expect(frame).toHaveAttribute('data-more-start')
    expect(frame).toHaveAttribute('data-more-end')

    widths.left = 600 // scrolled to the end
    fireEvent.scroll(region()!)
    expect(frame).toHaveAttribute('data-more-start')
    expect(frame).not.toHaveAttribute('data-more-end')

    widths.scroll = 300 // fits: no cue at all
    act(() => resize())
    expect(frame).not.toHaveAttribute('data-more-start')
    expect(frame).not.toHaveAttribute('data-more-end')
  })
})
