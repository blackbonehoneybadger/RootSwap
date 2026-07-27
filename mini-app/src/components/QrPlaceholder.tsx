/**
 * A visual QR-code substitute rendered as an inline SVG.
 * This is NOT a scannable QR code — the deposit address must be copied
 * manually. The pattern is deterministic per address, purely decorative.
 */

import { useLocale } from '../lib/locale'

const GRID = 17
const CELL = 8

function hashSeed(input: string): number {
  let h = 2166136261
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function cellOn(seed: number, x: number, y: number): boolean {
  let v = seed ^ Math.imul(x + 1, 374761393) ^ Math.imul(y + 1, 668265263)
  v = Math.imul(v ^ (v >>> 13), 1274126177)
  return ((v ^ (v >>> 16)) & 3) !== 0 && ((v >>> 5) & 1) === 1
}

function isFinderZone(x: number, y: number): boolean {
  const inCorner = (cx: number, cy: number) =>
    x >= cx && x < cx + 5 && y >= cy && y < cy + 5
  return inCorner(0, 0) || inCorner(GRID - 5, 0) || inCorner(0, GRID - 5)
}

function Finder({ cx, cy }: { cx: number; cy: number }) {
  return (
    <g>
      <rect x={cx * CELL} y={cy * CELL} width={5 * CELL} height={5 * CELL} fill="currentColor" />
      <rect x={(cx + 1) * CELL} y={(cy + 1) * CELL} width={3 * CELL} height={3 * CELL} fill="var(--card-bg, #1c1f26)" />
      <rect x={(cx + 2) * CELL} y={(cy + 2) * CELL} width={CELL} height={CELL} fill="currentColor" />
    </g>
  )
}

export function QrPlaceholder({ value }: { value: string }) {
  const { t } = useLocale()
  const seed = hashSeed(value)
  const size = GRID * CELL
  const cells: JSX.Element[] = []
  for (let y = 0; y < GRID; y++) {
    for (let x = 0; x < GRID; x++) {
      if (isFinderZone(x, y)) continue
      if (cellOn(seed, x, y)) {
        cells.push(
          <rect key={`${x}-${y}`} x={x * CELL} y={y * CELL} width={CELL} height={CELL} fill="currentColor" />,
        )
      }
    }
  }
  return (
    <div className="qr-placeholder" title={t('copyAddressManually')}>
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width="140"
        height="140"
        role="img"
        aria-label={t('copyAddressManually')}
      >
        {cells}
        <Finder cx={0} cy={0} />
        <Finder cx={GRID - 5} cy={0} />
        <Finder cx={0} cy={GRID - 5} />
      </svg>
      <div className="qr-placeholder-note">{t('copyAddressManually')}</div>
    </div>
  )
}
