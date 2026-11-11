import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { Button } from '../../../components'
import { GraphDrawing } from './GraphDrawing.tsx'
import { pictureName, type Picture } from './pictures.ts'
import { PHONE, useMediaQuery } from './useMediaQuery.ts'

/** One picture: a map illustration (a dark palette in dark mode, see global.css
 * `.situation-map`), a graph drawn from data, or a grid of pictures. */
export function PictureView({ picture, large }: { picture: Picture; large?: boolean }) {
  const phone = useMediaQuery(PHONE)
  if (picture.kind === 'map') {
    return (
      <img
        src={picture.map.src}
        alt={picture.map.alt}
        width={picture.map.width}
        height={picture.map.height}
        className="situation-map block h-auto w-full rounded-md"
      />
    )
  }
  if (picture.kind === 'drawing') {
    return <GraphDrawing drawing={picture.drawing} large={large ?? phone} />
  }
  return (
    <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0">
      {picture.items.map((item) => (
        <li key={item.caption}>
          <figure className="m-0 grid gap-1">
            <PictureView picture={item.picture} large={large} />
            <figcaption className="text-sm text-muted-foreground">{item.caption}</figcaption>
          </figure>
        </li>
      ))}
    </ul>
  )
}

export type PictureTab = { name: string; picture: Picture }

type PicturePanelProps = {
  tabs: readonly PictureTab[]
  caption?: string
  /** Which tab to show first; the panel resets to it when it changes (a new answer). */
  initial?: number
  /** Changes when the tabs mean something new, e.g. after each answer. */
  version?: string | number
}

/**
 * A picture in a question, with tabs when there is more than one (e.g. "Your graph | Campus
 * map"), so the picture switches in place and the map is never on the page twice. The tabs follow
 * the WAI-ARIA tabs pattern: arrow keys, Home and End move between them and select, only the
 * selected tab is in the tab order, and the panel is named by its tab. "View full size" opens the
 * picture in a dialog: Escape or the visible close button closes it, and focus goes back to the
 * button.
 */
export function PicturePanel({ tabs, caption, initial = 0, version }: PicturePanelProps) {
  const id = useId()
  const [selected, setSelected] = useState(initial)
  const [shownVersion, setShownVersion] = useState(version)
  if (version !== shownVersion) {
    setShownVersion(version)
    setSelected(initial)
  }
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const dialog = useRef<HTMLDialogElement>(null)
  const opener = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const current = tabs[Math.min(selected, tabs.length - 1)]

  const choose = (index: number) => {
    setSelected(index)
    tabRefs.current[index]?.focus()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = tabs.length - 1
    const next =
      event.key === 'ArrowRight'
        ? index === last
          ? 0
          : index + 1
        : event.key === 'ArrowLeft'
          ? index === 0
            ? last
            : index - 1
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : undefined
    if (next === undefined) return
    event.preventDefault()
    choose(next)
  }

  const openFull = () => {
    setOpen(true)
    const element = dialog.current
    if (element && typeof element.showModal === 'function') element.showModal()
  }
  const closeFull = () => {
    const element = dialog.current
    if (element?.open && typeof element.close === 'function') element.close()
    setOpen(false)
    opener.current?.focus()
  }

  const name = pictureName(current.picture)
  return (
    <figure
      className="m-0 grid gap-2 rounded-lg border border-border bg-card p-2"
      data-testid="picture-panel"
    >
      {tabs.length > 1 && (
        <div role="tablist" aria-label="Pictures" className="flex gap-1 border-b border-border">
          {tabs.map((tab, index) => (
            <button
              key={tab.name}
              ref={(element) => {
                tabRefs.current[index] = element
              }}
              type="button"
              role="tab"
              id={`${id}-tab-${index}`}
              aria-selected={index === selected}
              aria-controls={`${id}-panel`}
              tabIndex={index === selected ? 0 : -1}
              onClick={() => choose(index)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={`-mb-px border-b-[3px] px-3 py-1.5 text-sm ${
                index === selected
                  ? 'border-primary font-bold text-foreground'
                  : 'border-transparent font-medium text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.name}
            </button>
          ))}
        </div>
      )}
      <div
        id={`${id}-panel`}
        {...(tabs.length > 1
          ? { role: 'tabpanel', 'aria-labelledby': `${id}-tab-${selected}`, tabIndex: 0 }
          : {})}
        className="leading-none"
      >
        <PictureView picture={current.picture} />
      </div>
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>{caption ?? name}</span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={(event) => {
            opener.current = event.currentTarget
            openFull()
          }}
        >
          View full size
        </Button>
      </figcaption>
      <dialog
        ref={dialog}
        aria-label={`${current.name}, full size`}
        onClose={() => {
          setOpen(false)
          opener.current?.focus()
        }}
        className="m-0 h-full max-h-none w-full max-w-none bg-background p-3 text-foreground backdrop:bg-black/60"
      >
        {open && (
          <div className="grid gap-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">{current.name}</h2>
              <Button type="button" variant="secondary" size="sm" onClick={closeFull} autoFocus>
                Close
              </Button>
            </div>
            <div className="overflow-auto">
              <div className="min-w-[640px]">
                <PictureView picture={current.picture} large />
              </div>
            </div>
          </div>
        )}
      </dialog>
    </figure>
  )
}
