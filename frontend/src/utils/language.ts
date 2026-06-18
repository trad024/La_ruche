export type SupportedLanguage = 'ar' | 'fr' | 'en'

const ARABIC_RE = /[\u0600-\u06FF]/
const FRENCH_RE = /\b(?:bonjour|bonsoir|salut|merci|portefeuille|march[eé]|rapport|analyse|fran[cç]ais|s'il|vous|est-ce|quels?|quelles?)\b/i

export function detectLanguage(text: string): SupportedLanguage {
  if (ARABIC_RE.test(text)) return 'ar'
  if (FRENCH_RE.test(text)) return 'fr'
  return 'en'
}

export function languageToLocale(language: SupportedLanguage) {
  if (language === 'ar') return 'ar-SA'
  if (language === 'fr') return 'fr-FR'
  return 'en-US'
}

export function isRtl(text: string) {
  return detectLanguage(text) === 'ar'
}

export function languageInstruction(language: SupportedLanguage) {
  if (language === 'ar') {
    return 'Respond in Arabic. Use a clear professional tone. Do not mix French or English unless the user asks.'
  }
  if (language === 'fr') {
    return 'Respond in French. Use a clear professional tone. Do not mix English unless the user asks.'
  }
  return 'Respond in English. Use a clear professional tone.'
}
