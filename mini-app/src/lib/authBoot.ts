/**
 * Separates authentication from locale/theme so language switches never
 * re-send Telegram initData (backend rejects replays).
 */

export type AuthFn = () => Promise<unknown>

/**
 * Run auth exactly once for the app lifetime of this module instance.
 * Subsequent calls await the same promise (or return immediately if done).
 */
export function createAuthOnce(authFn: AuthFn): {
  run: () => Promise<unknown>
  calls: () => number
  reset: () => void
} {
  let promise: Promise<unknown> | null = null
  let callCount = 0

  return {
    run: () => {
      if (!promise) {
        callCount += 1
        promise = authFn()
      }
      return promise
    },
    calls: () => callCount,
    reset: () => {
      promise = null
      callCount = 0
    },
  }
}
