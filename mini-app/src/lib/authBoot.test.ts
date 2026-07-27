import { describe, expect, it, vi } from 'vitest'
import { createAuthOnce } from './authBoot'

describe('createAuthOnce', () => {
  it('calls authTelegram only once even when locale would change', async () => {
    const authFn = vi.fn(async () => ({ ok: true }))
    const once = createAuthOnce(authFn)

    await once.run()
    // simulate RU → EN locale change triggering another boot attempt
    await once.run()
    await once.run()

    expect(authFn).toHaveBeenCalledTimes(1)
    expect(once.calls()).toBe(1)
  })
})
