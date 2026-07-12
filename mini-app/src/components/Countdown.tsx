import { useEffect, useRef, useState } from 'react'
import { fmtCountdown, secondsUntil } from '../lib/format'

interface CountdownProps {
  expiresAt: string
  prefix?: string
  onExpire?: () => void
}

/** Live mm:ss countdown to an ISO timestamp. */
export function Countdown({ expiresAt, prefix, onExpire }: CountdownProps) {
  const [seconds, setSeconds] = useState(() => secondsUntil(expiresAt))
  const firedRef = useRef(false)

  useEffect(() => {
    firedRef.current = false
    setSeconds(secondsUntil(expiresAt))
    const timer = window.setInterval(() => {
      setSeconds(secondsUntil(expiresAt))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [expiresAt])

  useEffect(() => {
    if (seconds <= 0 && !firedRef.current) {
      firedRef.current = true
      onExpire?.()
    }
  }, [seconds, onExpire])

  const expired = seconds <= 0
  return (
    <span className={`countdown ${expired ? 'countdown-expired' : ''}`}>
      {prefix ? `${prefix} ` : ''}
      {expired ? 'истекло' : fmtCountdown(seconds)}
    </span>
  )
}
