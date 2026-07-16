import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  detectLocale,
  persistLocale,
  t,
  type Locale,
  type MsgKey,
} from './i18n'

export interface LocaleCtx {
  locale: Locale
  setLocale: (l: Locale) => void
  t: (key: MsgKey) => string
}

const LocaleContext = createContext<LocaleCtx | null>(null)

export function LocaleProvider({
  telegramLang,
  children,
}: {
  telegramLang?: string
  children: ReactNode
}) {
  const [locale, setLocaleState] = useState<Locale>(() => detectLocale(telegramLang))

  const setLocale = useCallback((l: Locale) => {
    persistLocale(l)
    setLocaleState(l)
  }, [])

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: (key: MsgKey) => t(locale, key),
    }),
    [locale, setLocale],
  )

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useLocale(): LocaleCtx {
  const ctx = useContext(LocaleContext)
  if (!ctx) throw new Error('LocaleProvider missing')
  return ctx
}
