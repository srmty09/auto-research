# Auto Research

An autonomous research and task agent that takes a high-level goal, plans its own steps, uses tools to gather information and execute actions, and produces a structured deliverable with minimal human intervention.

## Architecture

```
User Goal → Planner (LLM) → Tool Selection → Execution → Observation → loop → Final Output
```

The agent runs a **ReAct (Reason + Act)** loop powered by the Groq API. At each step it thinks, decides whether to use a tool or deliver the final answer, observes the result, and repeats until the goal is complete.

### Components

| Component | Responsibility |
|---|---|
| **Planner/Orchestrator** | LLM reasons about the goal and decides the next action |
| **Tool Layer** | Executes concrete actions: web search, code execution, file I/O |
| **Memory** | Short-term scratchpad of steps taken during the run |
| **Execution Loop** | Runs the Thought → Action → Observation cycle until done |
| **FastAPI Backend** | REST API with JWT auth, SQLite storage, agent orchestration |
| **Web Frontend** | SPA with login, session management, live results |

## Tools

| Tool | Description |
|---|---|
| `web_search` | DuckDuckGo search — returns snippets + URLs |
| `web_fetch` | Fetches and extracts readable text from a URL |
| `execute_code` | Sandboxed Python execution (30s timeout) |
| `save_file` | Writes content to the workspace directory |
| `read_file` | Reads content from the workspace directory |
| `list_files` | Lists all files in the workspace directory |
| `get_session_history` | Reviews past session results |

## Tech Stack

- **LLM**: Groq API (default: `llama-3.3-70b-versatile`)
- **Agent Loop**: Hand-rolled ReAct in Python with function calling
- **Search**: DuckDuckGo (free, no API key needed)
- **Code Sandbox**: Restricted subprocess with timeout
- **Backend**: FastAPI with SQLAlchemy + SQLite
- **Auth**: JWT tokens (bcrypt password hashing)
- **Frontend**: Vanilla JS SPA (dark theme)
- **Storage**: SQLite database + JSON session fallback

## Setup

```bash
pip install -r requirements.txt

# Edit .env with your Groq API key (already configured)
# JWT_SECRET is pre-set but change in production

uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

### Streamlit (legacy)

The original Streamlit UI is still available at `app.py`:

```bash
streamlit run app.py
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register a new user |
| POST | `/api/auth/login` | No | Login, get JWT token |
| GET | `/api/auth/me` | Yes | Current user info |
| POST | `/api/agent/run` | Yes | Run agent on a goal |
| POST | `/api/agent/followup` | Yes | Follow-up on a session |
| GET | `/api/sessions` | Yes | List user's sessions |
| GET | `/api/sessions/{id}` | Yes | Get session details |
| DELETE | `/api/sessions/{id}` | Yes | Delete a session |
| DELETE | `/api/sessions` | Yes | Clear all sessions |

## Evaluation

Run `python evaluate.py` to test the agent against 7 fixed tasks (4 simple, 3 multi-step). Results are logged with success rate, steps, and timing.

## Design Decisions

- **Hand-rolled ReAct** over LangGraph for maximum learning value and minimal dependencies
- **Groq over Claude** for fast inference and generous free tier
- **DuckDuckGo over Tavily** — no API key required, works out of the box
- **Function calling** format for structured tool use rather than text-parsed ReAct
- **FastAPI + vanilla JS** over heavier frameworks for simplicity and minimal dependencies
- **SQLite** for zero-config database, no external services needed

## Project Structure

```
├── main.py              # FastAPI entry point
├── app.py               # Streamlit UI (legacy)
├── evaluate.py          # Evaluation runner
├── requirements.txt
├── .env                 # API keys + JWT secret (not committed)
├── database.py          # SQLAlchemy setup
├── models.py            # SQLAlchemy models (User, Session)
├── schemas.py           # Pydantic request/response schemas
├── auth.py              # JWT + bcrypt auth utilities
├── routers/
│   ├── auth.py          # Register, login, me endpoints
│   ├── agent.py         # Run, follow-up endpoints
│   └── sessions.py      # Session CRUD endpoints
├── static/
│   ├── index.html       # SPA frontend
│   ├── style.css        # Dark theme styles
│   └── app.js           # Frontend logic
├── src/
│   ├── agent.py         # ReAct loop orchestration
│   ├── llm.py           # Groq API client
│   ├── tools.py         # Tool implementations and registry
│   ├── memory.py        # Conversation memory / scratchpad
│   ├── config.py        # Configuration (model, API key)
│   └── session_store.py # JSON-based session persistence
└── workspace/           # Saved files land here (gitignored)
```

## Limitations

- No persistent long-term memory (vector store)
- Single-agent setup (no delegation to sub-agents)
- Code execution uses a basic subprocess sandbox (no Docker/E2B)
- DuckDuckGo may rate-limit heavy use
