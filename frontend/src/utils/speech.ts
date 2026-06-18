import { detectLanguage, languageToLocale, type SupportedLanguage } from './language'

type SpeakOptions = {
  rate?: number
  pitch?: number
  onStart?: () => void
  language?: SupportedLanguage
}

const PREFERRED_NAMES: Record<SupportedLanguage, string[]> = {
  en: ['aria', 'jenny', 'guy', 'samantha', 'alex', 'daniel', 'google us english'],
  fr: ['denise', 'henri', 'thomas', 'audrey', 'google français', 'google francais'],
  ar: ['hoda', 'naayf', 'maged', 'tarik', 'google العربية', 'ar'],
}

function pickVoice(voices: SpeechSynthesisVoice[], language: SupportedLanguage) {
  const locale = languageToLocale(language).toLowerCase()
  const family = language
  const languageVoices = voices.filter(voice => voice.lang.toLowerCase().startsWith(family))
  const preferredNames = PREFERRED_NAMES[language]

  return (
    languageVoices.find(voice => voice.lang.toLowerCase() === locale && preferredNames.some(name => voice.name.toLowerCase().includes(name))) ??
    languageVoices.find(voice => voice.lang.toLowerCase() === locale) ??
    languageVoices.find(voice => preferredNames.some(name => voice.name.toLowerCase().includes(name))) ??
    languageVoices[0] ??
    null
  )
}

function loadVoices() {
  const synth = window.speechSynthesis
  const voices = synth.getVoices()
  if (voices.length) return Promise.resolve(voices)

  return new Promise<SpeechSynthesisVoice[]>(resolve => {
    const timeout = window.setTimeout(() => resolve(synth.getVoices()), 350)
    const onVoicesChanged = () => {
      window.clearTimeout(timeout)
      synth.removeEventListener('voiceschanged', onVoicesChanged)
      resolve(synth.getVoices())
    }
    synth.addEventListener('voiceschanged', onVoicesChanged)
  })
}

export async function speakLocalized(text: string, options: SpeakOptions = {}) {
  if (!('speechSynthesis' in window)) return

  const language = options.language ?? detectLanguage(text)
  const voices = await loadVoices()
  const utterance = new SpeechSynthesisUtterance(text)
  const voice = pickVoice(voices, language)

  utterance.lang = voice?.lang ?? languageToLocale(language)
  utterance.voice = voice
  utterance.rate = options.rate ?? 0.96
  utterance.pitch = options.pitch ?? (language === 'ar' ? 0.98 : 0.94)

  return new Promise<void>(resolve => {
    window.speechSynthesis.cancel()
    utterance.onstart = options.onStart ?? null
    utterance.onend = () => resolve()
    utterance.onerror = () => resolve()
    window.speechSynthesis.speak(utterance)
  })
}
