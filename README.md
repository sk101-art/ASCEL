# ASCEL

> A local-first AI coding assistant with a searchable skill vault, contextual retrieval, and controlled healing workflows.

ASCEL captures reusable solutions from engineering conversations and makes them available to future coding sessions. It combines a FastAPI service, SQLite with FTS5 search, local Ollama inference, an event-driven distillation worker, and a Next.js frontend.

## Features

- Stores conversation turns in a local SQLite journal.
- Distills solved engineering problems into reusable skills.
- Searches the skill vault with FTS5 and optional Ollama embeddings.
- Injects relevant skills into future coding prompts.
- Routes retrieved knowledge through a trust ladder before applying fixes.
- Supports explicit execution and verification probes.
- Streams skill events through Server-Sent Events.
- Provides skill search, preview, history, and deletion endpoints.

## Architecture

```text
Next.js frontend
      │
      ▼
FastAPI API ───────► SQLite + FTS5 skill vault
      │                         ▲
      ├──► Ollama chat          │
      ├──► Retriever ───────────┘
      └──► Healing engine

Conversation triggers ───► Distiller worker ───► Structured skills
```

## Core components

| Component | Responsibility |
| --- | --- |
| `main.py` | FastAPI application, chat endpoints, skill APIs, and SSE |
| `database.py` | SQLite schema and FTS5 synchronization |
| `retriever.py` | Keyword and embedding-based skill retrieval |
| `distiller.py` | Converts conversation trigger files into skills |
| `healing_engine.py` | Executes approved fixes and verification probes |
| `executor.py` | Command execution support |
| `frontend/` | Next.js interface |
| `ascel.db` | Local SQLite skill vault |

## Requirements

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/)
- Ollama model: `qwen2.5:3b`

```bash
ollama pull qwen2.5:3b
```

Install the Python packages required by the backend modules, including FastAPI, Uvicorn, Pydantic, Requests, Watchdog, NumPy, and Tiktoken.

## Run the backend

```bash
python database.py
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Useful endpoints:

- Health check: `http://127.0.0.1:8000/health`
- Interactive API docs: `http://127.0.0.1:8000/docs`

Run the API and distillation worker together:

```bash
python run_all.py
```

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Request flow

1. `POST /chat` receives a coding question.
2. ASCEL loads conversation history and searches the skill vault.
3. A relevant match is added to the local Ollama prompt.
4. Responses may include explicit `<execute>` and `<probe>` blocks.
5. The healing engine executes the workflow according to its trust tier.
6. `POST /save-skill` can trigger asynchronous skill distillation.

## Trust tiers

- **Suggest-Only** — recommends a solution without applying it automatically.
- **Auto-Apply with Notify** — applies a stronger match and reports the action.
- **Silent Auto-Heal** — reserved for the highest-confidence matches.

When Ollama is unavailable, retrieval falls back to deterministic keyword ranking.

## Testing

```bash
python test_retrieval.py
python test_dedupe.py
python test_collision.py
python test_healer.py
python test_phase2.py
python test_phase3.py
python e2e_test.py
```

## Security notes

- The default deployment stores conversations locally in `ascel.db`.
- Review generated commands before enabling automatic healing.
- Tighten the development CORS configuration before exposing the API beyond localhost.
- Do not commit private conversations, secrets, or production credentials.

## Project status

ASCEL is an evolving engineering prototype. APIs and workflow details may change as the skill vault and healing controls mature.

## License

No license file is currently included. Add a license before distributing ASCEL publicly.
