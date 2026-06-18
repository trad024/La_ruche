# LaRuche Current App - Visual Architecture Plan

## Purpose

This file is the single-source visual plan for the current LaRuche application. It documents what exists today: product features, UI routes, assistant modes, voice flows, document upload/OCR, the agent mesh, local models, auth modes, deployment topology, and the verification paths that keep the system honest.

Done means a reviewer can open only this file and understand how the app works end to end, which services are involved, where the code lives, and what still needs a production decision.

> [!NOTE]
> This is a current-state architecture plan, not a redesign proposal. It intentionally maps the running LaRuche app as implemented in the repo, including the recent instant/deep chat, voice-to-voice, document extraction, multilingual TTS, and LaRuche branding work.

## Product Snapshot

LaRuche is a private wealth intelligence workspace with five main web surfaces:

- **Overview**: live portfolio snapshot, AUM, performance, allocation, and top-level status.
- **Portfolio**: portfolio metrics, deals, allocation, periods, and performance drilldown.
- **Markets**: market quotes and macro indicators.
- **AI Assistant**: ChatGPT-like advisor with text, instant/deep modes, speech-to-text dictation, voice-to-voice conversation, and multi-file attachments.
- **Voice Studio**: voice service status and voice-focused controls.

The app runs locally at `http://localhost:5173/` in dev mode, with the FastAPI orchestrator on `:8000`, specialist agents on `:8001` through `:8005`, the voice service on `:8006`, and Ollama on `:11434`.

| Surface | Route / file | Current capability |
| --- | --- | --- |
| Overview | `/`, `frontend/src/pages/Dashboard.tsx` | Portfolio overview, LaRuche branding, animated logo assets, advisor workspace shell. |
| Portfolio | `/portfolio`, `frontend/src/pages/Portfolio.tsx` | AUM, TWR, IRR, Sharpe, volatility, deals, allocation, time-range controls. |
| Markets | `/market`, `frontend/src/pages/Market.tsx` | Quotes and macro indicators from the market endpoint and market agent. |
| AI Assistant | `/chat`, `frontend/src/pages/Chat.tsx` | SSE chat, instant/deep mode, reasoning UI, speech-to-text, voice-to-voice, file attachments. |
| Voice Studio | `/voice`, `frontend/src/pages/Voice.tsx` | Voice status, STT/TTS health, and voice service visibility. |
| Auth | `frontend/src/auth/*`, `libs/agentkit/src/agentkit/auth/jwt.py` | Dev bypass with `VITE_DEV_AUTH=true`; Keycloak PKCE/JWT when `KEYCLOAK_URL` is set. |

## System Map

**LaRuche local runtime and agent mesh.**

```mermaid
flowchart TB
  user[Advisor / Client Browser]
  web[React + Vite Web App :5173]
  auth[Auth Layer: Dev token or Keycloak PKCE]
  orch[Orchestrator FastAPI + LangGraph :8000]
  voice[Voice Service STT/TTS :8006]
  ollama[Ollama local models :11434]
  financial[Financial Agent :8001]
  market[Market Agent :8002]
  docs[Docs Agent :8003]
  action[Action Agent :8004]
  qa[QA Agent :8005]
  qdrant[Qdrant vector store :6333]
  mailhog[MailHog SMTP/Web :1025/:8025]
  postgres[PostgreSQL :5432]
  redis[Redis :6379]
  langfuse[Langfuse :3000]
  mlflow[MLflow :5000]

  user --> web
  web --> auth
  web -->|/api/chat SSE| orch
  web -->|/api/portfolio, /api/market| orch
  web -->|/voice-api/*| voice
  web -->|/api/attachments/extract| orch

  orch -->|A2A task envelope| financial
  orch -->|A2A task envelope| market
  orch -->|A2A task envelope| docs
  orch -->|A2A task envelope| action
  orch -->|A2A task envelope| qa
  orch -->|image OCR llava:7b| ollama
  voice -->|voice chat calls /api/chat| orch
  voice -->|faster-whisper / Piper fallback path| voice

  docs --> qdrant
  docs --> ollama
  market --> ollama
  financial --> ollama
  action --> mailhog
  orch --> postgres
  orch --> redis
  orch --> langfuse
  qa --> mlflow
```

## Core Runtime Services

| Service | Port | Role | Key implementation |
| --- | --- | --- | --- |
| Frontend | 5173 | React/Vite workspace UI | `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx` |
| Orchestrator | 8000 | Auth-protected API, LangGraph supervisor, SSE chat, attachments, GDPR | `services/orchestrator/src/orchestrator/main.py`, `graph.py` |
| Financial Agent | 8001 | Portfolio analytics and financial answers | `services/agent-financial/src/agent_financial/*` |
| Market Agent | 8002 | Market quotes and economic indicators | `services/agent-market/src/agent_market/*` |
| Docs Agent | 8003 | RAG over demo docs and attached file context | `services/agent-docs/src/agent_docs/main.py`, `vector_store.py` |
| Action Agent | 8004 | Report, email, WhatsApp stub with confirmation guard | `services/agent-action/src/agent_action/main.py` |
| QA Agent | 8005 | Generate and run pytest smoke tests | `services/agent-qa/src/agent_qa/main.py` |
| Voice Service | 8006 | STT, TTS, voice-to-voice wrapper | `services/voice/src/voice/main.py` |
| Ollama | 11434 | Local LLM, OCR model, embedding/model backend | `qwen2.5:3b`, `llava:7b`, `nomic-embed-text` when installed |

## Chat And Reasoning Flow

The assistant has two response modes:

- **Instant**: route visible user intent to the specialist mesh and stream final answer tokens.
- **Deep**: emit a separate `reasoning` SSE payload for the UI, execute the same mesh, then stream only the clean final answer. The final text must not leak `Reasoning summary`, `Checks performed`, or `Final answer` scaffolding.

**Instant and deep assistant execution.**

```mermaid
sequenceDiagram
  participant U as User
  participant C as Chat.tsx
  participant API as streamChat()
  participant O as Orchestrator /api/chat
  participant G as LangGraph graph.py
  participant A as Specialist agents

  U->>C: Type prompt / attach files / choose Instant or Deep
  C->>C: Build display_message plus hidden execution_message
  C->>API: POST /api/chat with mode and conversation_id
  API->>O: SSE request
  O->>O: guardrails.check_message()
  alt Deep mode
    O->>G: run_deep_turn_payloads(display_message, execution_message)
    G-->>API: data: {"reasoning": "..."}
  else Instant mode
    O->>G: run_turn(display_message, execution_message)
  end
  G->>G: route visible user intent by keyword rules
  G->>A: A2A tasks with full execution context
  A-->>G: grounded specialist output
  G->>G: aggregate and sanitize answer
  G-->>API: data: {"token": "..."}
  API-->>C: token or reasoning chunks
  C-->>U: ChatGPT-like reasoning UI plus final answer
```

> [!NOTE]
> Deep mode emulates reasoning outside the model with a planner/checker wrapper. The UI may show a temporary reasoning summary, but the final answer remains a normal assistant message. This avoids fake chain-of-thought while still giving the user a visible "thinking" affordance.

## Voice And Multilingual Behavior

There are two different voice features in the assistant composer:

- **Microphone button near the mode selector**: speech-to-text dictation. It transcribes audio and writes the transcript into the prompt input.
- **Blue right button**: voice-to-voice session. The user speaks, the voice service transcribes, the orchestrator answers, and the frontend speaks the reply. The session can continue until End.

Language handling is split between prompt steering and browser speech synthesis:

- `frontend/src/utils/language.ts` detects Arabic, French, and English.
- `frontend/src/utils/speech.ts` chooses browser voices by locale and preferred voice names.
- Arabic messages render RTL via `isRtl()`.
- Voice service backend uses `faster-whisper` when installed, and a safe dev fallback when heavy ML dependencies are absent.

**Voice-to-text and voice-to-voice paths.**

```mermaid
flowchart LR
  mic[Browser microphone]
  recorder[MediaRecorder + silence detection]
  dictation[Dictation mode]
  conversation[Voice session mode]
  voiceapi[Voice service :8006]
  orch[Orchestrator :8000]
  tts[Browser speech synthesis / Piper fallback]
  input[Prompt input]
  chat[Chat timeline]

  mic --> recorder
  recorder --> dictation
  recorder --> conversation
  dictation -->|POST /voice/transcribe| voiceapi
  voiceapi -->|transcript| input
  conversation -->|POST /voice/chat| voiceapi
  voiceapi -->|POST /api/chat| orch
  orch -->|SSE answer collected| voiceapi
  voiceapi -->|transcript + answer_text + audio_b64| chat
  chat --> tts
```

## Document, OCR, And Attachment Flow

The assistant supports multiple files at once, capped at 12 files and 8 MB per file in the current demo configuration. Supported categories:

- Text: `.txt`, `.md`, `.csv`, `.json`, `text/*`
- Images: `.png`, `.jpg`, `.jpeg`, `.webp`, `image/*`
- Audio: `.wav`, `.mp3`, `.m4a`, `.webm`, `.ogg`, `audio/*`

Images use Ollama OCR through `MODEL_OCR`, defaulting to `llava:7b`. Audio attachments are sent to the voice service for transcription. Extracted context is appended to the hidden execution prompt under `Attached file context:`.

**Multi-file attachment extraction and docs-agent grounding.**

```mermaid
flowchart TB
  files[User selects files in Chat.tsx]
  extract[POST /api/attachments/extract]
  typecheck{File type}
  text[Decode text file]
  image[Image OCR via Ollama llava:7b]
  audio[Audio transcription via voice service]
  context[ExtractedAttachment[]]
  prompt[Hidden execution prompt with Attached file context]
  router[Orchestrator router]
  docs[Docs Agent]
  answer[Answer using attached context only]

  files --> extract
  extract --> typecheck
  typecheck --> text
  typecheck --> image
  typecheck --> audio
  text --> context
  image --> context
  audio --> context
  context --> prompt
  prompt --> router
  router --> docs
  docs --> answer
```

> [!TIP]
> If the user asks to summarize uploaded documents but no attachment context exists, the orchestrator now replies that no uploaded file context is available instead of inventing a portfolio answer.

## Agent Mesh

The mesh is real service-to-service communication, not just UI labels. The orchestrator routes to specialists over A2A HTTP task envelopes. Each agent exposes an Agent Card and a `chat` skill through `agentkit.a2a.router`.

| Agent | Trigger examples | Tools / data | Safety behavior |
| --- | --- | --- | --- |
| Financial | `portfolio`, `AUM`, `TWR`, `IRR`, `Sharpe`, `volatility` | Portfolio seed data, finance metrics, LLM fallback | Sanitizes signoffs and identity placeholders at aggregation. |
| Market | `market`, `stock`, `inflation`, `yield`, `S&P`, `nasdaq` | MarketQuoteTool, EconIndicatorTool, MarketOverviewTool | System prompt says use only supplied tool data. |
| Docs | `document`, `uploaded`, `attached`, `pdf`, `search` | Qdrant when available, in-memory lexical fallback, direct attachment context | Attached context path forbids seeded demo facts. |
| Action | `send`, `email`, `whatsapp`, `generate report` | ReportBuildTool, EmailSendTool, WhatsAppSendTool | Outbound email/WhatsApp require `confirmed=true`. |
| QA | `test`, `validate`, `check api`, `functional` | LLM generated pytest plus subprocess sandbox | Generated code is sanitized and falls back to known-good tests. |

## API Surface

### POST /api/chat

Stream assistant response

**Auth:** Bearer token or dev bypass

**Request content type:** application/json

**Request example:**

```json
{ "message": "what is my portfolio?", "display_message": "what is my portfolio?", "conversation_id": "uuid", "mode": "instant" }
```

**Responses:**

- `200`: SSE stream with token and optional reasoning payloads.

```json
data: {"reasoning":"..."}\n\ndata: {"token":"Your portfolio ..."}\n\ndata: [DONE]
```

- `400`: Guardrail violation for prompt injection or unsafe message.

Main assistant endpoint. Deep mode separates `reasoning` payloads from `token` payloads so the frontend can render a temporary thinking block without polluting the final answer.

### POST /api/attachments/extract

Extract readable context from text, image, and audio files

**Auth:** Bearer token or dev bypass

**Request content type:** multipart/form-data

**Request example:**

```json
files[]=brief.txt, files[]=screenshot.png, files[]=voice.webm
```

**Responses:**

- `200`: List of extracted attachment contexts.

```json
{ "attachments": [{ "name": "brief.txt", "kind": "text", "content": "..." }] }
```

Used by the plus button in the chat composer. OCR depends on Ollama and `MODEL_OCR`, default `llava:7b`.

### POST /voice/chat

Voice-to-voice turn

**Auth:** Forwarded Authorization header when available

**Request content type:** multipart/form-data

**Request example:**

```json
audio=recording.webm, conversation_id=uuid
```

**Responses:**

- `200`: Transcript, answer text, synthesized answer audio.

```json
{ "transcript": "What is my AUM?", "answer_text": "...", "answer_audio_b64": "..." }
```

The voice service transcribes the audio, calls the orchestrator chat endpoint, collects the SSE answer, then synthesizes audio.

## Source Map

### Important repo paths

- `frontend/src/App.tsx` (modified): Protected routes for Overview, Portfolio, Markets, AI Assistant, and Voice Studio.
- `frontend/src/components/Layout.tsx` (modified): LaRuche shell, sidebar navigation, user state, sign out.
- `frontend/src/pages/Chat.tsx` (modified): Composer, instant/deep mode, reasoning UI, dictation, voice session, attachments.
- `frontend/src/utils/language.ts` (added): Arabic/French/English detection, RTL support, response language instruction.
- `frontend/src/utils/speech.ts` (added): Browser voice selection by detected language and locale.
- `services/orchestrator/src/orchestrator/main.py` (modified): Chat SSE, attachment extraction, OCR status, GDPR endpoints.
- `services/orchestrator/src/orchestrator/graph.py` (modified): LangGraph router, A2A fan-out, deep reasoning payloads, attachment-context guard.
- `services/agent-docs/src/agent_docs/main.py` (modified): RAG search plus direct attached-file context path.
- `services/voice/src/voice/main.py` (modified): STT, TTS, and voice-to-voice orchestration.
- `docker-compose.dev.yml` (modified): Local infra: Traefik, Keycloak, Postgres, Redis, Qdrant, MailHog, Langfuse, MLflow.
- `helm/wealthmesh` (modified): Kubernetes/Helm deployment for orchestrator, agents, voice, and backing services.

## Data And Infra Model

### Entities

#### UserContext

| Field | Type | Key |
| --- | --- | --- |
| user_id | string | PK |
| email | string |  |
| roles | list[string] |  |

#### ChatRequest

| Field | Type | Key |
| --- | --- | --- |
| message | string |  |
| display_message | string |  |
| conversation_id | string |  |
| mode | instant \| deep |  |

#### MeshState

| Field | Type | Key |
| --- | --- | --- |
| user_message | string |  |
| execution_message | string |  |
| routed_agents | list[string] |  |
| agent_results | list[dict] |  |
| final_answer | string |  |

#### ExtractedAttachment

| Field | Type | Key |
| --- | --- | --- |
| name | string |  |
| kind | text \| image \| audio \| unsupported |  |
| content | string |  |
| error | string nullable |  |

#### A2ATask

| Field | Type | Key |
| --- | --- | --- |
| task_id | string | PK |
| skill_id | string |  |
| messages | list[A2AMessage] |  |
| context | dict |  |

### Relations

- user_context -> chat_request (1-n)
- chat_request -> mesh_state (1-1)
- chat_request -> attachment (1-n)
- mesh_state -> agent_task (1-n)

## Deployment Modes

### Local dev

- Frontend runs with Vite on `:5173`.
- Backend services run as local uvicorn processes on `:8000` to `:8006`.
- `KEYCLOAK_URL` unset enables backend dev bypass.
- `VITE_DEV_AUTH=true` gives the frontend a `dev-token`.
- Ollama runs on host `:11434`; OCR readiness depends on `llava:7b`.
- Infrastructure can be started with `docker compose -f docker-compose.dev.yml up -d`.

### Docker / Kubernetes

- Docker Compose provides local infra containers: Traefik, Keycloak, Postgres, Redis, Qdrant, MailHog, Langfuse, MLflow.
- Helm chart in `helm/wealthmesh` deploys orchestrator, agents, voice, and backing services.
- Minikube script exists at `scripts/minikube-start.sh`.
- Helm values point agents to `host.docker.internal:11434` for Ollama in dev-like cluster mode.

## Security, Compliance, And Guardrails

- **Auth**: `get_current_user()` returns a dev advisor when `KEYCLOAK_URL` is unset; otherwise it validates Keycloak RS256 JWTs against JWKS, issuer, and allowed clients.
- **Prompt safety**: `agentkit.guardrails.check_message()` rejects prompt injection and unsafe extraction requests before agents run.
- **Action safety**: email and WhatsApp tools require explicit `confirmed=true` before sending/logging outbound actions.
- **GDPR**: `DELETE /api/gdpr/delete-my-data` logs an erasure request; production notes call for cascading to Postgres, Qdrant, and Langfuse.
- **AI transparency**: the UI labels the AI assistant and warning copy says LaRuche can make mistakes.
- **Local model posture**: Ollama keeps LLM/OCR traffic local when models are installed and running.

## Verification Matrix

- [x] All local services respond on health endpoints: 8000 through 8006.
- [x] Frontend loads at http://localhost:5173/ with LaRuche title and dev auth.
- [x] Instant prompt `what is my portfolio?` streams a portfolio answer.
- [x] Deep prompt emits a separate reasoning event and no final-answer scaffold leak.
- [x] Document question without attachments says no uploaded file context exists.
- [x] Attached file context is answered from the attachment instead of seeded demo docs.
- [x] Email action drafts and asks for `confirmed=true` before sending.
- [x] French and Arabic prompts answer in matching language; Arabic UI text is RTL.
- [x] `uv run pytest services/orchestrator/tests/test_auth.py services/orchestrator/tests/test_graph.py services/agent-docs/tests/test_docs_agent.py` passes.

## Known Gaps And Production Decisions

> [!WARNING]
> The current voice backend still forces faster-whisper transcription with `language="en"` in `services/voice/src/voice/main.py`. The frontend can choose French/Arabic/English TTS voices, but backend STT language auto-detection or per-locale model routing is still the next production-quality step.

| Area | Current state | Production direction |
| --- | --- | --- |
| STT language | Backend faster-whisper prompt is English-biased. | Add language auto-detect or pass frontend-detected locale to voice service. |
| TTS quality | Browser SpeechSynthesis plus Piper fallback. | Install per-language Piper voices or move to a stronger local TTS stack. |
| Docs persistence | Attachments are per request; docs agent has demo in-memory store plus optional Qdrant. | Persist uploaded docs with ownership, retention, deletion, and vector lifecycle. |
| Action approvals | Tool requires `confirmed=true`, but UI confirmation flow can be stronger. | Add explicit confirmation modal and audit trail display. |
| Market data | Seed/static tool data and limited symbol handling. | Plug current market provider and cache freshness metadata. |
| Reasoning wrapper | Plan/critique summary is deterministic outside the model. | Add task-specific verifier checks and measurable confidence flags. |
| Kubernetes | Helm/minikube assets exist. | Decide whether final demo runs local uvicorn, Docker Compose, or minikube. |

### Open Questions

#### Which runtime should be the main demo path?

This changes how startup docs, scripts, and troubleshooting should be written.

- Local uvicorn plus Vite (recommended): Fastest for development and live debugging.
- Docker Compose: Cleaner for infrastructure parity but heavier for the Python services.
- Minikube / Helm: Best for deployment story, slower for laptop iteration.

#### How production-like should voice become?

The UI is in place; the next choice is model/runtime quality.

- Keep current stack (recommended): Good enough for demo; improve error messages and install checks.
- Local multilingual STT/TTS: Better French/Arabic/English voice quality, more setup work.
- External realtime API: Best quality and latency, but changes privacy and deployment assumptions.

#### Should the visual plan include a future UI redesign phase?

- Keep this architecture-only (recommended): Use this file as the technical map.
- Add UI redesign phase: Extend with page-by-page redesign tasks and visual QA.
