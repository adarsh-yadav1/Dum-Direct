import { useEffect, useId, useRef, type ReactNode } from 'react'

import { button } from './styles'


/** The seal on a dum pot: a sealed lid with a band of dough around it. */
export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 font-display text-xl font-bold tracking-tight text-ink">
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
        <circle cx="13" cy="13" r="11.5" fill="var(--color-indigo)" />
        <circle cx="13" cy="13" r="7.5" fill="none" stroke="var(--color-saffron)" strokeWidth="2.5" />
        <circle cx="13" cy="13" r="2.2" fill="var(--color-saffron)" />
      </svg>
      DumDirect
    </span>
  )
}

/** The Indian food-labelling mark: a square with a dot, green for vegetarian, red for non-vegetarian. */
export function VegMark({ veg }: { veg: boolean }) {
  const colour = veg ? 'var(--color-veg)' : 'var(--color-nonveg)'
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" role="img" aria-label={veg ? 'Vegetarian' : 'Non-vegetarian'} className="shrink-0">
      <rect x="1" y="1" width="14" height="14" rx="2" fill="var(--color-surface)" stroke={colour} strokeWidth="1.5" />
      <circle cx="8" cy="8" r="4" fill={colour} />
    </svg>
  )
}

const TINTS = ['#e6e8f6', '#f3e6d3', '#dfeee6', '#f1dfe3', '#e3ebf4']

/** A dish photo, or a quiet tile with its initial when there is no photo (or it fails to load). */
export function DishTile({ name, src, tintKey, size = 88 }: { name: string; src: string | null; tintKey: number; size?: number }) {
  const style = { width: size, height: size }
  if (src) {
    return (
      <img
        src={src}
        alt=""
        loading="lazy"
        width={size}
        height={size}
        style={style}
        className="rounded-xl bg-indigo-wash object-cover"
        onError={(e) => {
          e.currentTarget.style.visibility = 'hidden'
        }}
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      style={{ ...style, backgroundColor: TINTS[tintKey % TINTS.length] }}
      className="inline-flex items-center justify-center rounded-xl font-display text-3xl font-bold text-indigo"
    >
      {name.charAt(0)}
    </span>
  )
}

/** A modal that slides up from the bottom on phones and centres on larger screens. */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose()
      }}
      className="m-0 mt-auto max-h-[92dvh] w-full max-w-none overflow-y-auto rounded-t-2xl bg-surface p-0 text-ink md:m-auto md:max-w-lg md:rounded-2xl"
    >
      {open && (
        <div className="p-5">
          <div className="mb-3 flex items-start justify-between gap-4">
            <h2 id={titleId} className="text-xl font-bold">{title}</h2>
            <button type="button" onClick={onClose} className={button.quiet} aria-label="Close">Close</button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  )
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-lg border border-late/30 bg-late/5 px-3.5 py-2.5 text-sm text-late">
      {children}
    </p>
  )
}
