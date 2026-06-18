import { useEffect, useRef, useState } from 'react'
import {
  AudioLines,
  Bot,
  Check,
  ChevronDown,
  Mail,
  MessageCircle,
  Mic,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  User,
  X,
} from 'lucide-react'
import {
  extractAttachments,
  runVoiceChat,
  streamChat,
  transcribeAudio,
  type ChatMessage,
  type ExtractedAttachment,
} from '../api/client'
import { useAuth } from '../auth/useAuth'
import { detectLanguage, isRtl, languageInstruction } from '../utils/language'
import { speakLocalized } from '../utils/speech'

type ListeningMode = 'dictation' | 'conversation' | null
type VoicePhase = 'idle' | 'listening' | 'processing' | 'speaking'
type ResponseMode = 'instant' | 'deep'
type ToolConfirmation = {
  kind: 'email' | 'whatsapp'
  target: string
  label: string
}
type ToolStatus = 'pending' | 'running' | 'approved' | 'denied'
type UiChatMessage = ChatMessage & {
  responseMode?: ResponseMode
  reasoning?: string
  startedAt?: number
  completedAt?: number
  sourceRequest?: string
  toolConfirmation?: ToolConfirmation
  toolStatus?: ToolStatus
}

function nowMs() {
  return Date.now()
}

export default function Chat() {
  const { token } = useAuth()
  const [messages, setMessages] = useState<UiChatMessage[]>([
    { role: 'assistant', content: 'Hello! I\'m your LaRuche advisor. How can I help you today?' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listeningMode, setListeningMode] = useState<ListeningMode>(null)
  const [voicePhase, setVoicePhase] = useState<VoicePhase>('idle')
  const [voiceSessionActive, setVoiceSessionActive] = useState(false)
  const [responseMode, setResponseMode] = useState<ResponseMode>('instant')
  const [attachments, setAttachments] = useState<ExtractedAttachment[]>([])
  const [voiceNotice, setVoiceNotice] = useState('')
  const [convId] = useState(() => crypto.randomUUID())
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const voiceSessionRef = useRef(false)
  const animationRef = useRef<number | null>(null)
  const maxRecordingRef = useRef<number | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => () => {
    voiceSessionRef.current = false
    recorderRef.current?.stop()
    streamRef.current?.getTracks().forEach(track => track.stop())
    if (animationRef.current) cancelAnimationFrame(animationRef.current)
    if (maxRecordingRef.current) window.clearTimeout(maxRecordingRef.current)
    window.speechSynthesis?.cancel()
  }, [])

  async function send(
    message = input,
    speakReply = false,
    options: { displayMessage?: string; mode?: ResponseMode } = {},
  ) {
    const cleanMessage = message.trim() || (attachments.length ? 'Please analyze the attached files.' : '')
    if (!cleanMessage || loading) return

    const activeMode = options.mode ?? responseMode
    const language = detectLanguage(cleanMessage)
    const attachmentLabel = attachments.length
      ? `\n\nAttached: ${attachments.map(file => file.name).join(', ')}`
      : ''
    const context = attachments.length
      ? `\n\nAttached file context:\n${attachments.map(file => (
          `[${file.kind}] ${file.name}\n${file.content || file.error || 'No readable content extracted.'}`
        )).join('\n\n')}`
      : ''
    const modeInstruction = activeMode === 'deep'
      ? '\n\nResponse format: include conclusion, evidence, assumptions, risks, and next actions when useful. Do not reveal hidden chain-of-thought.'
      : '\n\nResponse format: answer directly and briefly. Do not repeat the user question.'
    const actionContext = buildActionContext(cleanMessage, messages)
    const personaInstruction = `\n\nAdvisor style: You are LaRuche, not WealthMesh. ${languageInstruction(language)} Do not sign as [Your Name], and do not add email-style signoffs.`
    const requestMessage = `${cleanMessage}${context}${actionContext}${modeInstruction}${personaInstruction}`
    const sourceRequest = `${cleanMessage}${actionContext}`
    const visibleMessage = options.displayMessage ?? `${cleanMessage}${attachmentLabel}`

    setInput('')
    setAttachments([])
    setVoiceNotice('')
    const assistantStartedAt = nowMs()
    setMessages(prev => [
      ...prev,
      { role: 'user', content: visibleMessage },
      { role: 'assistant', content: '', responseMode: activeMode, startedAt: assistantStartedAt, sourceRequest },
    ])
    setLoading(true)

    let response = ''
    try {
      for await (const chunk of streamChat(requestMessage, convId, token, activeMode, visibleMessage)) {
        if (chunk.type === 'reasoning') {
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            updated[updated.length - 1] = {
              ...last,
              reasoning: [last.reasoning, chunk.content].filter(Boolean).join('\n\n'),
            }
            return updated
          })
          continue
        }
        response += chunk.content
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { ...updated[updated.length - 1], role: 'assistant', content: response }
          return updated
        })
      }
      if (speakReply && response.trim()) void speak(response)
    } catch {
      const fallback = 'I could not reach the advisory mesh. Please try again.'
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: fallback,
          responseMode,
          startedAt: assistantStartedAt,
          completedAt: nowMs(),
        }
        return updated
      })
      if (speakReply) void speak(fallback)
    } finally {
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        const toolConfirmation = parseToolConfirmation(response)
        if (last?.role === 'assistant' && last.responseMode === activeMode && !last.completedAt) {
          updated[updated.length - 1] = {
            ...last,
            completedAt: nowMs(),
            toolConfirmation: toolConfirmation ?? last.toolConfirmation,
            toolStatus: toolConfirmation ? 'pending' : last.toolStatus,
          }
        }
        return updated
      })
      setLoading(false)
    }
  }

  async function handleToolDecision(index: number, action: ToolConfirmation, approved: boolean) {
    const sourceRequest = messages[index]?.sourceRequest || messages[index - 1]?.content || ''

    if (!approved) {
      setMessages(prev => prev.map((message, messageIndex) => (
        messageIndex === index
          ? { ...message, toolStatus: 'denied', content: `${action.label} cancelled.` }
          : message
      )))
      return
    }

    setMessages(prev => prev.map((message, messageIndex) => (
      messageIndex === index ? { ...message, toolStatus: 'running' } : message
    )))

    const confirmedRequest = `${sourceRequest}\nconfirmed=true`
    const displayMessage = `Confirmed ${action.kind === 'email' ? 'email' : 'WhatsApp'} to ${action.target}`
    await send(confirmedRequest, false, { displayMessage, mode: 'instant' })

    setMessages(prev => prev.map((message, messageIndex) => (
      messageIndex === index ? { ...message, toolStatus: 'approved' } : message
    )))
  }

  async function startRecording(mode: Exclude<ListeningMode, null>) {
    setVoiceNotice('')
    if (!navigator.mediaDevices?.getUserMedia || !('MediaRecorder' in window)) {
      setVoiceNotice('Audio recording is not supported in this browser.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      const preferredType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
        .find(type => MediaRecorder.isTypeSupported(type))
      const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : undefined)

      chunksRef.current = []
      streamRef.current = stream
      recorderRef.current = recorder
      recorder.ondataavailable = event => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        cleanupRecording()
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        if (blob.size < 800) {
          setListeningMode(null)
          setVoicePhase('idle')
          setVoiceNotice('No audio was captured. Check the selected microphone and try again.')
          return
        }
        if (mode === 'dictation') void finishDictation(blob)
        else void finishVoiceTurn(blob)
      }

      recorder.start(250)
      setListeningMode(mode)
      setVoicePhase('listening')
      if (mode === 'conversation') watchForSilence(stream)
      maxRecordingRef.current = window.setTimeout(() => stopRecording(true), mode === 'conversation' ? 20_000 : 60_000)
    } catch (error) {
      const name = error instanceof DOMException ? error.name : ''
      setVoiceNotice(
        name === 'NotAllowedError'
          ? 'Microphone access is blocked. Allow microphone access for localhost, then try again.'
          : name === 'NotFoundError'
            ? 'No microphone was found. Connect or select a microphone and try again.'
            : 'The microphone could not start. Check your browser audio settings.',
      )
      setListeningMode(null)
      setVoicePhase('idle')
    }
  }

  function stopRecording(processAudio: boolean) {
    const recorder = recorderRef.current
    if (!recorder || recorder.state === 'inactive') return
    if (!processAudio) {
      recorder.onstop = () => cleanupRecording()
      chunksRef.current = []
    }
    recorder.stop()
  }

  function cleanupRecording() {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    recorderRef.current = null
    if (animationRef.current) cancelAnimationFrame(animationRef.current)
    animationRef.current = null
    if (maxRecordingRef.current) window.clearTimeout(maxRecordingRef.current)
    maxRecordingRef.current = null
  }

  function watchForSilence(stream: MediaStream) {
    const audioContext = new AudioContext()
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 512
    audioContext.createMediaStreamSource(stream).connect(analyser)
    const samples = new Uint8Array(analyser.fftSize)
    const startedAt = nowMs()
    let heardVoice = false
    let quietSince = 0

    const measure = () => {
      if (!recorderRef.current || recorderRef.current.state === 'inactive') {
        void audioContext.close()
        return
      }
      analyser.getByteTimeDomainData(samples)
      const rms = Math.sqrt(samples.reduce((sum, value) => {
        const normalized = (value - 128) / 128
        return sum + normalized * normalized
      }, 0) / samples.length)
      const now = nowMs()
      if (rms > 0.035) {
        heardVoice = true
        quietSince = 0
      } else if (heardVoice) {
        quietSince ||= now
        if (now - quietSince > 1100 && now - startedAt > 1400) {
          stopRecording(true)
          void audioContext.close()
          return
        }
      }
      animationRef.current = requestAnimationFrame(measure)
    }
    animationRef.current = requestAnimationFrame(measure)
  }

  async function finishDictation(blob: Blob) {
    setListeningMode(null)
    setVoicePhase('processing')
    setVoiceNotice('Transcribing your message...')
    try {
      const result = await transcribeAudio(blob)
      if (!result.transcript.trim()) throw new Error('Empty transcript')
      setInput(result.transcript.trim())
      setVoiceNotice('Dictation ready. Review the text and press send.')
    } catch {
      setVoiceNotice('The audio could not be transcribed. Check that the voice service is online.')
    } finally {
      setVoicePhase('idle')
    }
  }

  async function finishVoiceTurn(blob: Blob) {
    setListeningMode(null)
    setVoicePhase('processing')
    setVoiceNotice('The voice agent is thinking...')
    try {
      const result = await runVoiceChat(blob, convId, token)
      const transcript = result.transcript.trim()
      const answer = result.answer_text.trim()
      if (!transcript) throw new Error('Empty transcript')
      setMessages(prev => [
        ...prev,
        { role: 'user', content: transcript },
        { role: 'assistant', content: answer || 'I could not answer that voice request.' },
      ])
      if (answer) {
        await speak(answer)
      }
      if (voiceSessionRef.current) {
        setVoiceNotice('Listening for your next question...')
        await startRecording('conversation')
      }
    } catch {
      setVoiceNotice('The voice agent could not complete that turn. Press the blue button to try again.')
      endVoiceSession()
    }
  }

  async function startVoiceSession() {
    voiceSessionRef.current = true
    setVoiceSessionActive(true)
    setVoiceNotice('Listening. Speak naturally and pause when you are finished.')
    await startRecording('conversation')
  }

  function endVoiceSession() {
    voiceSessionRef.current = false
    setVoiceSessionActive(false)
    stopRecording(false)
    window.speechSynthesis?.cancel()
    setListeningMode(null)
    setVoicePhase('idle')
    setVoiceNotice('')
  }

  function speak(text: string) {
    return speakLocalized(text, {
      rate: 0.96,
      pitch: 0.94,
      onStart: () => {
        setVoicePhase('speaking')
        setVoiceNotice('Voice agent is speaking...')
      },
    })
  }

  async function attachFiles(fileList?: FileList | null) {
    const files = Array.from(fileList ?? [])
    if (!files.length) return
    setVoiceNotice('')
    try {
      setVoiceNotice('Extracting text from attachments...')
      const extracted = await extractAttachments(files)
      setAttachments(prev => [...prev, ...extracted])
      setVoiceNotice(`${extracted.length} attachment${extracted.length > 1 ? 's' : ''} ready.`)
    } catch {
      setVoiceNotice('Those files could not be attached.')
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const isListening = listeningMode !== null

  return (
    <div className="page chat-page">
      <header className="chat-header">
        <div className="chat-heading">
          <div className="page-icon"><Sparkles className="h-5 w-5" /></div>
          <div>
            <h1>AI Assistant</h1>
            <p>Type, dictate, or start a natural voice conversation.</p>
          </div>
        </div>
        <div className="online-badge"><span className="status-dot status-dot-ready" /> Advisory mesh online</div>
      </header>

      <section className="chat-panel">
        <div className="message-list">
          <div className="message-column">
            {messages.map((message, index) => (
              <div key={index} className={`message-row ${message.role === 'user' ? 'message-row-user' : ''}`}>
                {message.role === 'assistant' && (
                  <div className="message-avatar"><Bot className="h-4 w-4" /></div>
                )}
                {message.role === 'assistant' ? (
                  <AssistantMessage
                    message={message}
                    isStreaming={loading && index === messages.length - 1}
                    onToolDecision={(action, approved) => void handleToolDecision(index, action, approved)}
                  />
                ) : (
                  <div
                    className={`message-bubble message-bubble-user ${isRtl(message.content) ? 'message-bubble-rtl' : ''}`}
                    dir={isRtl(message.content) ? 'rtl' : 'ltr'}
                  >
                    {message.content}
                  </div>
                )}
                {message.role === 'user' && (
                  <div className="message-avatar message-avatar-user"><User className="h-4 w-4" /></div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="chat-composer">
          <div className={`composer-box ${isListening ? 'composer-box-listening' : ''}`}>
            <input
              ref={fileInputRef}
              className="composer-file-input"
              type="file"
              multiple
              accept=".txt,.md,.csv,.json,.png,.jpg,.jpeg,.webp,.wav,.mp3,.m4a,.webm,.ogg,text/plain,text/markdown,text/csv,application/json,image/*,audio/*"
              onChange={event => void attachFiles(event.target.files)}
            />
            <button
              className="composer-icon-button composer-plus"
              onClick={() => fileInputRef.current?.click()}
              aria-label="Attach files"
              title="Attach text, image, or audio files"
            >
              <Plus className="h-5 w-5" />
            </button>

            <div className="composer-entry">
              {attachments.slice(0, 3).map((file, fileIndex) => (
                <div className="composer-attachment" key={`${file.name}-${fileIndex}`} title={file.error || file.name}>
                  <Paperclip className="h-3 w-3" />
                  <span>{file.kind}: {file.name}</span>
                  <button
                    onClick={() => setAttachments(prev => prev.filter((_, index) => index !== fileIndex))}
                    aria-label={`Remove ${file.name}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
              {attachments.length > 3 && <span className="composer-attachment-more">+{attachments.length - 3}</span>}
              <input
                className="composer-input"
                placeholder={isListening ? 'Listening...' : 'Ask LaRuche anything'}
                value={input}
                onChange={event => setInput(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter' && !event.shiftKey) void send()
                }}
                disabled={loading}
              />
            </div>

            <label className="composer-mode" title="Response mode">
              <select
                value={responseMode}
                onChange={event => setResponseMode(event.target.value as ResponseMode)}
                aria-label="Response mode"
              >
                <option value="instant">Instant</option>
                <option value="deep">Deep</option>
              </select>
              <ChevronDown className="h-4 w-4" />
            </label>

            <button
              className={`composer-icon-button composer-mic ${listeningMode === 'dictation' ? 'composer-control-active' : ''}`}
              onClick={() => listeningMode === 'dictation' ? stopRecording(true) : void startRecording('dictation')}
              disabled={loading || voiceSessionActive || voicePhase === 'processing'}
              aria-label={listeningMode === 'dictation' ? 'Stop dictation' : 'Dictate message'}
              title="Speech to text"
            >
              <Mic className="h-5 w-5" />
            </button>

            {voiceSessionActive ? (
              <button className="composer-stop" onClick={endVoiceSession} aria-label="End voice conversation">
                <span className="mini-wave" aria-hidden="true"><i /><i /><i /><i /></span>
                End
              </button>
            ) : input.trim() || attachments.length ? (
              <button
                className="composer-primary"
                onClick={() => void send()}
                disabled={loading || (!input.trim() && !attachments.length)}
                aria-label="Send message"
              >
                <Send className="h-5 w-5" />
              </button>
            ) : (
              <button
                className="composer-primary composer-voice"
                onClick={() => void startVoiceSession()}
                disabled={loading || listeningMode === 'dictation' || voicePhase === 'processing'}
                aria-label="Start voice conversation"
                title="Voice to voice"
              >
                <AudioLines className="h-5 w-5" />
              </button>
            )}
          </div>
          <p className={`composer-hint ${voiceNotice ? 'composer-hint-error' : ''}`}>
            {voiceNotice || (listeningMode === 'dictation'
                ? 'Dictating only. Press the microphone again to convert your speech into text.'
                : voicePhase === 'listening'
                  ? 'Voice agent is listening and will answer aloud.'
                : 'LaRuche can make mistakes. Verify important financial information.')}
          </p>
        </div>
      </section>
    </div>
  )
}

function AssistantMessage({
  message,
  isStreaming,
  onToolDecision,
}: {
  message: UiChatMessage
  isStreaming: boolean
  onToolDecision: (action: ToolConfirmation, approved: boolean) => void
}) {
  const parsed = parseDeepResponse(message.content)
  const reasoningText = message.reasoning || parsed.reasoningText
  const shouldUseReasoningUi = message.responseMode === 'deep' && Boolean(reasoningText)
  const finalContent = parsed.hasReasoning ? parsed.finalAnswer : message.content
  const toolConfirmation = message.toolConfirmation ?? parseToolConfirmation(finalContent)
  const isRtlMessage = isRtl(finalContent)

  return (
    <div
      className={`message-bubble ${isRtlMessage ? 'message-bubble-rtl' : ''}`}
      dir={isRtlMessage ? 'rtl' : 'ltr'}
    >
      {shouldUseReasoningUi && (
        parsed.finalAnswer ? (
          <details className="reasoning-collapse">
            <summary>
              <span className="reasoning-dot" />
              Reasoning for {formatReasoningDuration(message)}
            </summary>
            <div className="reasoning-details">{reasoningText}</div>
          </details>
        ) : (
          <div className="reasoning-live">
            <span className="reasoning-dot reasoning-dot-live" />
            <div>
              <strong>Thinking...</strong>
              <p>{reasoningText || 'Building a plan, checking the available data, and preparing a clean answer.'}</p>
            </div>
          </div>
        )
      )}
      {toolConfirmation ? (
        <ToolConfirmationCard
          action={toolConfirmation}
          status={message.toolStatus ?? 'pending'}
          onApprove={() => onToolDecision(toolConfirmation, true)}
          onDeny={() => onToolDecision(toolConfirmation, false)}
        />
      ) : (
        <div className="assistant-answer">
          {finalContent || (isStreaming ? 'Thinking...' : '')}
        </div>
      )}
    </div>
  )
}

function ToolConfirmationCard({
  action,
  status,
  onApprove,
  onDeny,
}: {
  action: ToolConfirmation
  status: ToolStatus
  onApprove: () => void
  onDeny: () => void
}) {
  const Icon = action.kind === 'email' ? Mail : MessageCircle
  const isPending = status === 'pending'

  return (
    <div className={`tool-confirm-card tool-confirm-card-${status}`}>
      <div className="tool-confirm-icon">
        <Icon className="h-4 w-4" />
      </div>
      <div className="tool-confirm-body">
        <div className="tool-confirm-kicker">Tool confirmation</div>
        <h3>{action.label}</h3>
        <p>
          LaRuche is asking permission before it uses this external action.
          {action.kind === 'email' ? ' The message will be sent by the configured email service.' : ' The WhatsApp action is currently logged by the dev stub.'}
        </p>
        <div className="tool-confirm-target">
          <span>Destination</span>
          <strong>{action.target}</strong>
        </div>
        {isPending ? (
          <div className="tool-confirm-actions">
            <button className="tool-confirm-deny" onClick={onDeny}>
              <X className="h-4 w-4" />
              Deny
            </button>
            <button className="tool-confirm-approve" onClick={onApprove}>
              <Check className="h-4 w-4" />
              Confirm
            </button>
          </div>
        ) : (
          <div className="tool-confirm-status">
            {status === 'running' && 'Running action...'}
            {status === 'approved' && 'Approved. The confirmed request was submitted; see the tool result below.'}
            {status === 'denied' && 'Denied. No action was sent.'}
          </div>
        )}
      </div>
    </div>
  )
}

function parseDeepResponse(content: string) {
  const finalMarker = 'Final answer'
  const reasoningStart = content.indexOf('Reasoning summary')
  const finalStart = content.indexOf(finalMarker)

  if (reasoningStart === -1 && finalStart === -1) {
    return { hasReasoning: false, reasoningText: '', finalAnswer: content }
  }

  const reasoningEnd = finalStart === -1 ? content.length : finalStart
  const reasoningText = content
    .slice(reasoningStart === -1 ? 0 : reasoningStart, reasoningEnd)
    .replace(/^Reasoning summary\s*/i, '')
    .trim()
  const finalAnswer = finalStart === -1
    ? ''
    : content.slice(finalStart + finalMarker.length).trim()

  return { hasReasoning: true, reasoningText, finalAnswer }
}

function parseToolConfirmation(content: string): ToolConfirmation | null {
  const emailMatch = content.match(/Confirm email to\s+([^?\s]+)\?\s*Set confirmed=true to send\./i)
  if (emailMatch?.[1]) {
    return {
      kind: 'email',
      target: emailMatch[1],
      label: 'Send email',
    }
  }

  const whatsappMatch = content.match(/Confirm WhatsApp to\s+(.+?)\?\s*Set confirmed=true\.?/i)
  if (whatsappMatch?.[1]) {
    return {
      kind: 'whatsapp',
      target: whatsappMatch[1].trim(),
      label: 'Send WhatsApp',
    }
  }

  return null
}

function buildActionContext(message: string, history: UiChatMessage[]) {
  if (!isActionRequest(message)) return ''
  if (!/\b(?:this|it|that|those informations?|these informations?|previous answer|last answer)\b/i.test(message)) {
    return ''
  }

  const previousAnswer = [...history]
    .reverse()
    .find(item => item.role === 'assistant' && item.content.trim() && !parseToolConfirmation(item.content))
    ?.content
    .trim()

  if (!previousAnswer) return ''
  return `\n\nContent to send:\n${previousAnswer}`
}

function isActionRequest(message: string) {
  return /\b(?:send|email|mail|whatsapp|notify|share)\b/i.test(message)
}

function formatReasoningDuration(message: UiChatMessage) {
  if (!message.startedAt) return 'a moment'
  const finishedAt = message.completedAt ?? nowMs()
  const seconds = Math.max(1, Math.round((finishedAt - message.startedAt) / 1000))
  return `${seconds}s`
}
