import { useEffect, useRef, useState } from 'react'

interface CopyButtonProps {
  value: string
  small?: boolean
}

/** Copies a value to the clipboard with brief visual feedback. */
export function CopyButton({ value, small = false }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    }
  }, [])

  const copy = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value)
      } else {
        // fallback for insecure contexts
        const ta = document.createElement('textarea')
        ta.value = value
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      setCopied(true)
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
      timerRef.current = window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <button
      type="button"
      className={`copy-btn ${small ? 'copy-btn-small' : ''}`}
      onClick={copy}
      aria-label="Скопировать"
    >
      {copied ? '✓ Скопировано' : 'Копировать'}
    </button>
  )
}
