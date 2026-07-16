import { createContext, useContext } from 'react';
import type { Locale, MsgKey } from './i18n';

export interface LocaleCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: MsgKey) => string;
}

export const LocaleContext = createContext<LocaleCtx | null>(null);

export function useLocale(): LocaleCtx {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error('LocaleContext missing');
  return ctx;
}
