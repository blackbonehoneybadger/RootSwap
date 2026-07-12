import type { QuoteSourceType } from '../lib/types'
import { sourceTypeLabel } from '../lib/format'

/** Colored badge for the quote/order source type (DEMO / SANDBOX / REAL). */
export function SourceBadge({ source }: { source: QuoteSourceType }) {
  return (
    <span className={`badge badge-source badge-source-${source.toLowerCase()}`}>
      {sourceTypeLabel(source)}
    </span>
  )
}
