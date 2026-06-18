import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  Activity,
  AudioLines,
  CircleStop,
  Headphones,
  Mic,
  Play,
  Radio,
  RotateCcw,
  Sparkles,
  Volume2,
  Waves,
} from 'lucide-react'
import {
  getVoiceStatus,
  runVoiceChat,
  streamChat,
  synthesizeSpeech,
  transcribeAudio,
  type VoiceStatus,
} from '../api/client'
import { useAuth } from '../auth/useAuth'
import { speakLocalized } from '../utils/speech'

type Mode = 'conversation' | 'transcribe' | 'synthesize'
type BrowserRecognition = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onstart: (() => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  onresult: ((event: {
    results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }>
  }) => void) | null
}
type RecognitionConstructor = new () => BrowserRecognition

export default function Voice() {
  const { token } = useAuth()
  const [mode, setMode] = useState<Mode>('conversation')
  const [status, setStatus] = useState<VoiceStatus | null>(null)
  const [recording, setRecording] = useState(false)
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [answer, setAnswer] = useState('')
  const [ttsText, setTtsText] = useState('Your portfolio is positioned for resilient long-term growth.')
  const [error, setError] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const recognitionRef = useRef<BrowserRecognition | null>(null)
  const transcriptRef = useRef('')
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)
  const conversationId = useRef(crypto.randomUUID())

  useEffect(() => {
    getVoiceStatus().then(setStatus).catch(() => setStatus(null))
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
      recognitionRef.current?.stop()
    }
  }, [])

  async function startRecording() {
    setError('')
    setTranscript('')
    setAnswer('')
    transcriptRef.current = ''

    const speechWindow = window as Window & {
      SpeechRecognition?: RecognitionConstructor
      webkitSpeechRecognition?: RecognitionConstructor
    }
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition
    if (!status?.stt.ready && Recognition) {
      const recognition = new Recognition()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'en-US'
      recognition.onstart = () => beginTimer()
      recognition.onresult = event => {
        const text = Array.from(event.results)
          .map(result => result[0].transcript)
          .join(' ')
          .trim()
        transcriptRef.current = text
        setTranscript(text)
      }
      recognition.onerror = () => {
        setError('Browser speech recognition could not hear that clearly.')
        stopTimer()
      }
      recognition.onend = async () => {
        recognitionRef.current = null
        stopTimer()
        if (mode === 'conversation' && transcriptRef.current) {
          await answerSpokenQuestion(transcriptRef.current)
        }
      }
      recognitionRef.current = recognition
      recognition.start()
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = event => event.data.size && chunksRef.current.push(event.data)
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        await processRecording(blob)
      }
      recorderRef.current = recorder
      recorder.start()
      beginTimer()
    } catch {
      setError('Microphone access was not available. Check your browser permission.')
    }
  }

  function stopRecording() {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    } else {
      recorderRef.current?.stop()
    }
    stopTimer()
  }

  function beginTimer() {
    setElapsed(0)
    setRecording(true)
    timerRef.current = window.setInterval(() => setElapsed(value => value + 1), 1000)
  }

  function stopTimer() {
    setRecording(false)
    if (timerRef.current) window.clearInterval(timerRef.current)
  }

  async function answerSpokenQuestion(text: string) {
    setBusy(true)
    try {
      let response = ''
      for await (const chunk of streamChat(text, conversationId.current, token)) response += chunk
      const cleanResponse = response.trim()
      setAnswer(cleanResponse)
      if (cleanResponse) speakInBrowser(cleanResponse)
    } catch {
      setError('The advisory mesh could not answer that voice request.')
    } finally {
      setBusy(false)
    }
  }

  async function processRecording(blob: Blob) {
    setBusy(true)
    try {
      if (mode === 'transcribe') {
        const result = await transcribeAudio(blob)
        setTranscript(result.transcript)
      } else {
        const result = await runVoiceChat(blob, conversationId.current, token)
        setTranscript(result.transcript)
        setAnswer(result.answer_text)
        if (result.answer_audio_b64 && status?.tts.ready) {
          const source = `data:audio/wav;base64,${result.answer_audio_b64}`
          await new Audio(source).play()
        } else if (result.answer_text) {
          speakInBrowser(result.answer_text)
        }
      }
    } catch {
      setError('The voice service could not complete that request.')
    } finally {
      setBusy(false)
    }
  }

  function speakInBrowser(text: string) {
    void speakLocalized(text, { rate: 0.96, pitch: 0.92 })
  }

  async function synthesize() {
    if (!ttsText.trim()) return
    setBusy(true)
    setError('')
    try {
      if (!status?.tts.ready && 'speechSynthesis' in window) {
        speakInBrowser(ttsText)
      } else {
        const audio = await synthesizeSpeech(ttsText)
        const url = URL.createObjectURL(audio)
        await new Audio(url).play()
      }
    } catch {
      setError('Speech playback was not available.')
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setTranscript('')
    setAnswer('')
    setError('')
    setElapsed(0)
  }

  return (
    <div className="page voice-page">
      <PageIntro
        eyebrow="Natural interface"
        title="Voice Studio"
        description="Talk to your portfolio, turn meetings into text, or generate a spoken briefing."
        icon={<AudioLines className="h-5 w-5" />}
      />

      <div className="voice-mode-grid">
        <ModeCard
          active={mode === 'conversation'}
          icon={<Radio />}
          title="Voice to voice"
          text="Speak naturally and hear an AI advisory response."
          onClick={() => setMode('conversation')}
        />
        <ModeCard
          active={mode === 'transcribe'}
          icon={<Mic />}
          title="Speech to text"
          text="Capture a voice note and create a clean transcript."
          onClick={() => setMode('transcribe')}
        />
        <ModeCard
          active={mode === 'synthesize'}
          icon={<Volume2 />}
          title="Text to speech"
          text="Turn any portfolio briefing into spoken audio."
          onClick={() => setMode('synthesize')}
        />
      </div>

      <div className="voice-workspace">
        <section className="voice-console glass-panel">
          <div className="console-topline">
            <div>
              <span className="section-label">Live console</span>
              <h2>{mode === 'synthesize' ? 'Generate a briefing' : 'Start a voice session'}</h2>
            </div>
            <button className="icon-button" onClick={reset} aria-label="Reset voice session">
              <RotateCcw className="h-4 w-4" />
            </button>
          </div>

          {mode === 'synthesize' ? (
            <div className="tts-composer">
              <textarea
                value={ttsText}
                onChange={event => setTtsText(event.target.value)}
                placeholder="Write the text you want LaRuche to speak..."
              />
              <div className="composer-footer">
                <span>{ttsText.length} characters</span>
                <button className="primary-button" onClick={synthesize} disabled={busy || !ttsText.trim()}>
                  <Play className="h-4 w-4" />
                  {busy ? 'Preparing...' : 'Play briefing'}
                </button>
              </div>
            </div>
          ) : (
            <div className="recorder-stage">
              <div className={`voice-orb ${recording ? 'voice-orb-active' : ''}`}>
                <div className="voice-orb-inner">
                  {recording ? <Waves className="h-10 w-10" /> : <Mic className="h-10 w-10" />}
                </div>
                <span className="orbit orbit-one" />
                <span className="orbit orbit-two" />
              </div>
              <p className="recorder-state">
                {busy ? 'Processing your voice...' : recording ? 'Listening...' : 'Ready when you are'}
              </p>
              <p className="recorder-time">{formatTime(elapsed)}</p>
              <button
                className={`record-button ${recording ? 'record-button-stop' : ''}`}
                onClick={recording ? stopRecording : startRecording}
                disabled={busy}
              >
                {recording ? <CircleStop className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                {recording ? 'Stop recording' : 'Start recording'}
              </button>
              <p className="privacy-note">Audio is processed in memory and is not stored.</p>
            </div>
          )}

          {error && <div className="error-banner">{error}</div>}
        </section>

        <aside className="voice-sidebar">
          <section className="glass-panel engine-panel">
            <div className="panel-heading">
              <Activity className="h-4 w-4" />
              Voice engines
            </div>
            <EngineRow
              label="Speech recognition"
              value={status?.stt.ready ? status.stt.engine : 'browser speech recognition'}
              ready={Boolean(status)}
            />
            <EngineRow
              label="Speech generation"
              value={status?.tts.engine ?? 'Connecting...'}
              ready={status?.tts.ready ?? false}
            />
            <EngineRow label="Advisory pipeline" value="Online" ready={Boolean(status?.voice_to_voice)} />
          </section>

          <section className="glass-panel result-panel">
            <div className="panel-heading">
              <Headphones className="h-4 w-4" />
              Session output
            </div>
            <ResultBlock label="You said" value={transcript || 'Your transcript will appear here.'} />
            {mode === 'conversation' && (
              <ResultBlock label="LaRuche replied" value={answer || 'The spoken response will appear here.'} accent />
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}

function PageIntro({
  eyebrow,
  title,
  description,
  icon,
}: {
  eyebrow: string
  title: string
  description: string
  icon: ReactNode
}) {
  return (
    <header className="page-intro">
      <div className="page-icon">{icon}</div>
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </header>
  )
}

function ModeCard({
  active,
  icon,
  title,
  text,
  onClick,
}: {
  active: boolean
  icon: ReactNode
  title: string
  text: string
  onClick: () => void
}) {
  return (
    <button className={`mode-card ${active ? 'mode-card-active' : ''}`} onClick={onClick}>
      <span className="mode-icon">{icon}</span>
      <span>
        <strong>{title}</strong>
        <small>{text}</small>
      </span>
      {active && <Sparkles className="mode-spark h-4 w-4" />}
    </button>
  )
}

function EngineRow({ label, value, ready }: { label: string; value: string; ready: boolean }) {
  return (
    <div className="engine-row">
      <span className={`status-dot ${ready ? 'status-dot-ready' : ''}`} />
      <span>
        <small>{label}</small>
        <strong>{value}</strong>
      </span>
    </div>
  )
}

function ResultBlock({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`result-block ${accent ? 'result-block-accent' : ''}`}>
      <span>{label}</span>
      <p>{value}</p>
    </div>
  )
}

function formatTime(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}
