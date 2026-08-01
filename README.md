# AutonomIQ — Autonomous AI Interview Platform

> Built for **Ezitech** by **Wasid Khan** as an internship project.

- 🌐 **Live Frontend:** [https://autonomous-ai-interview-platform.vercel.app](https://autonomous-ai-interview-platform.vercel.app)
- ⚙️ **Backend API:** [https://autonai-interview-platform-bg.onrender.com](https://autonai-interview-platform-bg.onrender.com)

---
---

## What it does

AutonomIQ conducts full technical interviews autonomously — a candidate registers, answers spoken questions through their browser, and the platform produces a scored report for a human mentor to review. No interviewer is needed in the room.

The system adapts in real time: questions get harder as the candidate performs well, easier if they struggle, and a follow-up is asked when an answer is too vague to judge. A mentor sees the transcript, per-answer scores, and any tab-switching flags before making a final hire/reject decision.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Candidate                            │
│  Browser (React/Vite) ─── Mic ─── WebSocket ──► Render API  │
└──────────────────────────────────────────────────────────────┘
                                          │
           ┌──────────────────────────────┼──────────────────┐
           │                             │                    │
      Supabase                        Groq API           OpenAI API
      Postgres                    Whisper STT +        gpt-4o-mini-tts
  (sessions, scores,               LLaMA LLM              (TTS)
   audio blobs)
           │
        Pinecone
   (1,050 question vectors
    across 10 tech tracks)
```

**Backend:** FastAPI + LangGraph (stateful interview agent) + SQLAlchemy  
**Frontend:** React 18 + Vite + Tailwind CSS v4  
**Voice pipeline:** Browser `MediaRecorder` → WebSocket → Groq Whisper → LLaMA eval → OpenAI TTS  

---

## Features

| Area | What's built |
|---|---|
| Registration | Resume upload (PDF/DOCX), skill extraction, technology track + experience level selection |
| Interview engine | LangGraph-based stateful agent, adaptive difficulty, follow-up detection |
| Voice | Real-time WebSocket audio streaming, Groq-hosted Whisper transcription, TTS question audio |
| Difficulty pacing | 5-question tiers; juniors capped at medium; seniors start at medium |
| Anti-cheating | Tab/window focus-loss tracked per answer, surfaced to mentor |
| Evaluation | Per-answer rubric scoring (technical, problem-solving, communication), ESL-aware prompt |
| Mentor dashboard | Full transcript, per-answer scores, focus-loss flags, hire/review/reject override |
| Analytics | Completion rate, technology performance charts, candidate ranking, skill distribution, weekly volume |
| Resume after refresh | Interview state rebuilt from the database on any page load |
| Mentor auth | Shared key guard on all evaluation and analytics endpoints |

---

## Technology stack

### Backend
- **FastAPI** — async API and WebSocket server
- **LangGraph** — stateful interview graph (one turn per request)
- **Groq** — LLaMA 3.1 8B for answer evaluation and follow-up generation; Whisper large-v3-turbo for transcription
- **OpenAI** — gpt-4o-mini-tts for question audio
- **Pinecone** — vector store for 1,050 pre-embedded interview questions
- **fastembed** — ONNX Runtime embeddings (all-MiniLM-L6-v2, 384 dims); replaced PyTorch, cutting ~3.9 GB from the install
- **SQLAlchemy** — ORM over Supabase Postgres
- **psycopg2-binary** — Postgres driver

### Frontend
- **React 18** + **React Router v6**
- **Vite** (build)
- **Tailwind CSS v4**
- **Recharts** (analytics charts)
- **Axios**

---

## Question bank

1,050 questions across 10 technology tracks, generated with Groq LLaMA and calibrated for intern-level candidates:

| Track | Easy | Medium | Hard |
|---|---|---|---|
| AI | 40 | 40 | 25 |
| MERN | 40 | 40 | 25 |
| Laravel | 40 | 40 | 25 |
| Flutter | 40 | 40 | 25 |
| Python | 40 | 40 | 25 |
| DevOps | 40 | 40 | 25 |
| UI/UX | 40 | 40 | 25 |
| SQL | 40 | 40 | 25 |
| Data Structures | 40 | 40 | 25 |
| System Design | 40 | 40 | 25 |

Hard questions are reserved for senior candidates only. Junior candidates are capped at medium on their difficulty ladder. Questions are semantically deduplicated at generation time.

---

## Running locally

### Prerequisites
- Python 3.12
- Node 22+
- PostgreSQL (local) or a Supabase project
- API keys: Groq, OpenAI, Pinecone

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in .env with your API keys and database URL

uvicorn app.main:app --reload
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install

cp .env.example .env
# Set VITE_API_URL=http://localhost:8000

npm run dev
# UI at http://localhost:5173
```

### Seed the question bank

```bash
cd backend
python -m app.modules.question_bank.ingest
```

---

## Environment variables

### Backend (`.env`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (Session Pooler on Supabase, port 5432) |
| `GROQ_API_KEY` | LLaMA + Whisper |
| `OPENAI_API_KEY` | TTS audio |
| `PINECONE_API_KEY` | Question vector store |
| `PINECONE_INDEX_NAME` | Your Pinecone index name |
| `LLM_MODEL` | e.g. `llama-3.1-8b-instant` |
| `WHISPER_MODEL_SIZE` | e.g. `small` (only used when `ALLOW_LOCAL_WHISPER=true`) |
| `ALLOW_LOCAL_WHISPER` | `true` locally, `false` on Render (saves ~500 MB RAM) |
| `MENTOR_KEY` | Shared key for the mentor dashboard and analytics |
| `FRONTEND_ORIGINS` | Comma-separated allowed CORS origins |

### Frontend (`.env`)

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Backend base URL (e.g. `https://your-service.onrender.com`) |

---

## Deployment

### Database — Supabase

Render Postgres requires a card. We used **Supabase** instead (free tier, 500 MB).

Connection string: use the **Session Pooler** on **port 5432**.  
- Direct connection is IPv6-only — Render doesn't support IPv6 outbound.  
- Transaction Pooler (port 6543) doesn't support DDL; `create_all()` won't run.

Tables are created automatically by SQLAlchemy on first startup. No migration tool is needed.

### Backend — Render

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Env vars:** all seven from the table above
- Set `ALLOW_LOCAL_WHISPER=false` — the local Whisper model (~500 MB) does not fit the free tier's 512 MB RAM limit. Final transcription routes to Groq's API instead.
- Set Render's **build pipeline spend limit** to 0 in Workspace Settings → Build Pipeline (covers build minutes; bandwidth has no equivalent cap).

### Frontend — Vercel

- Set **Root Directory** to `frontend/`
- Set `VITE_API_URL` to your Render service URL before the first build (Vite inlines it at build time — changing it later requires a redeploy)
- `frontend/vercel.json` rewrites all paths to `index.html` so React Router handles client-side routing correctly

After Vercel deploys, go back to Render and set `FRONTEND_ORIGINS` to your Vercel domain.

---

## Known limitations

| Limitation | Reason | Fix at scale |
|---|---|---|
| Shared mentor key | No user auth system | Proper OAuth / user table |
| `/interviews/{id}/resume` is unauthenticated | No per-candidate session | Per-candidate JWT |
| Free tier sleeps after 15 min idle | Render free plan | Upgrade to Starter tier |
| ~1,600 interview cap on audio storage | Audio BLOBs in Postgres (free 500 MB) | Move to object storage (R2, S3) |
| Concurrency limited without Groq Whisper | Local Whisper serialises requests | Already mitigated — final transcription uses Groq |

---

## Project structure

```
autonomiq-interview-platform/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── db/             # SQLAlchemy models and session
│   │   ├── modules/
│   │   │   ├── agent/      # LangGraph interview graph
│   │   │   ├── evaluation/ # Scoring rubric and report generation
│   │   │   ├── question_bank/ # RAG ingestion and retrieval
│   │   │   └── voice/      # STT, TTS, audio buffer
│   │   ├── config.py
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api/            # Axios client
    │   └── pages/          # CandidateRegister, InterviewRoom, MentorDashboard, Analytics, MentorLogin
    ├── vercel.json
    └── package.json
```

---

## Test suite

```bash
cd backend
pytest -q -m "not integration"   # ~56 fast unit tests, no API keys needed
pytest -q                         # includes integration tests — needs live keys
```

---

## Decisions worth noting

**fastembed over sentence-transformers:** same model (`all-MiniLM-L6-v2`, 384 dims), but runs on ONNX Runtime instead of PyTorch. Verified identical vectors (cosine similarity 1.0000). Removed ~3.9 GB of PyTorch and orphaned CUDA libraries from the install, which is what made the free-tier RAM limit achievable.

**Audio in Postgres instead of disk:** Render's filesystem is ephemeral — it wipes on every deploy, restart, and (on free tier) every wake from sleep. At ~50 KB per question and 12 questions per interview, Postgres is the right trade-off at this scale. Acknowledged as a pattern that doesn't hold at thousands of concurrent interviews.

**Groq-hosted Whisper for concurrency:** a local Whisper model serialises every transcription request behind the last one. Ten candidates finishing answers simultaneously would queue behind each other. Groq's hosted endpoint handles concurrent requests independently, at no RAM cost on the server.

**Shared mentor key:** intentional for this scope. Full user authentication was out of scope for a two-week project. The key lives in an environment variable, is compared with `secrets.compare_digest` to resist timing attacks, and is documented as a known limitation with the obvious upgrade path.

---

## Author

**Wasid Khan** — BSCS 2026, University of Peshawar  
Intern at Ezitech Islamabad
