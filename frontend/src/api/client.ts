import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
})

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    delete api.defaults.headers.common['Authorization']
  }
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// ── Portfolio & market data ───────────────────────────────────────────────
export interface PortfolioSummary {
  aum_fmt: string
  twr_pct: number
  annualized_pct: number
  irr_pct: number
  sharpe: number
  volatility_pct: number
  profit_fmt: string
  num_deals: number
  num_active: number
}
export interface Allocation {
  geography: Record<string, number>
  sector: Record<string, number>
}
export interface Deal {
  name: string
  sector: string
  geo: string
  status: string
  aum: number
  twr: number
}
export interface MarketData {
  quotes: { symbol: string; name: string; price: number; change_pct: number }[]
  indicators: { key: string; name: string; value: number; unit: string; date: string }[]
}
export interface VoiceStatus {
  status: string
  stt: { engine: string; model: string; ready: boolean }
  tts: { engine: string; voice: string; ready: boolean }
  voice_to_voice: boolean
}
export interface VoiceChatResult {
  transcript: string
  answer_text: string
  answer_audio_b64: string
  conversation_id: string
}
export interface ExtractedAttachment {
  name: string
  kind: 'text' | 'image' | 'audio' | 'unsupported'
  content: string
  error?: string
}

export const getPortfolioSummary = () =>
  api.get<PortfolioSummary>('/api/portfolio/summary').then(r => r.data)
export const getAllocation = () => api.get<Allocation>('/api/portfolio/allocation').then(r => r.data)
export const getDeals = () => api.get<Deal[]>('/api/portfolio/deals').then(r => r.data)
export const getMarket = () => api.get<MarketData>('/api/market').then(r => r.data)
export const getVoiceStatus = () =>
  axios.get<VoiceStatus>('/voice-api/status').then(r => r.data)

export async function transcribeAudio(audio: Blob) {
  const body = new FormData()
  body.append('audio', audio, 'recording.webm')
  const { data } = await axios.post<{ transcript: string; model: string }>(
    '/voice-api/transcribe',
    body,
  )
  return data
}

export async function extractAttachments(files: File[]) {
  const body = new FormData()
  files.forEach(file => body.append('files', file, file.name))
  const { data } = await api.post<{ attachments: ExtractedAttachment[] }>(
    '/api/attachments/extract',
    body,
  )
  return data.attachments
}

export async function synthesizeSpeech(text: string) {
  const body = new FormData()
  body.append('text', text)
  const response = await axios.post('/voice-api/synthesize', body, { responseType: 'blob' })
  return response.data as Blob
}

export async function runVoiceChat(
  audio: Blob,
  conversationId: string,
  token: string | null,
) {
  const body = new FormData()
  body.append('audio', audio, 'recording.webm')
  body.append('conversation_id', conversationId)
  const { data } = await axios.post<VoiceChatResult>('/voice-api/chat', body, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  return data
}

export async function* streamChat(
  message: string,
  conversationId: string,
  token: string | null,
  mode: 'instant' | 'deep' = 'instant',
  displayMessage = message,
): AsyncGenerator<{ type: 'token' | 'reasoning'; content: string }> {
  const base = import.meta.env.VITE_API_URL ?? ''
  const resp = await fetch(`${base}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, display_message: displayMessage, conversation_id: conversationId, mode }),
  })

  if (!resp.ok || !resp.body) throw new Error(`Chat error: ${resp.status}`)

  const reader = resp.body.getReader()
  const dec = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          const payload = JSON.parse(line.slice(6))
          if (payload.reasoning) yield { type: 'reasoning', content: payload.reasoning }
          if (payload.token) yield { type: 'token', content: payload.token }
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}

export default api
