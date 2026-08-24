# Auto Research

An autonomous research and task agent that takes a high-level goal, plans its own steps, uses tools to gather information and execute actions, and produces a structured deliverable with minimal human intervention. Runs as a Streamlit app with per-user accounts, multi-turn chat, and a shared knowledge base.

## Architecture

```
User Goal → Agent (LangGraph ReAct loop) → Tool Selection → Execution → Observation → loop → Final Answer
```

The agent runs a **ReAct (Reason + Act)** loop built on `langgraph.prebuilt.create_react_agent`, powered by the DeepSeek API. At each step it thinks, decides whether to use a tool or deliver the final answer, observes the result, and repeats until the goal is complete. Follow-up messages continue the same conversation, so the agent keeps prior context.

An optional **multi-agent mode** uses a supervisor graph that delegates to specialist sub-agents (researcher, writer, coder) and compiles their outputs into a final answer.

### Components

| Component | Responsibility |
|---|---|
| **Agent** (`src/agent.py`) | ReAct loop orchestration, streaming events, follow-up turns |
| **Multi-Agent** (`src/multi_agent.py`) | Supervisor graph delegating to researcher/writer/coder specialists |
| **Tool Layer** (`src/tools.py`) | Executes concrete actions: web search, code execution, file I/O, vector search |
| **Memory** (`src/memory.py`) | Per-session conversation history carried across follow-up turns |
| **Vector Store** (`src/vector_store.py`) | Chroma-backed semantic search over uploaded files and saved reports |
| **User Store** (`src/user_store.py`) | Account registration/login (bcrypt) and per-user profile/preferences |
| **Session Store** (`src/session_store.py`) | JSON-based persistence of past research sessions, with tagging |
| **Cost Tracker** (`src/cost_tracker.py`) | Token usage and cost accounting per session/user |
| **Streamlit UI** (`streamlit_app.py`) | Chat interface, login, sessions, file upload, usage stats |

## Tools

| Tool | Description |
|---|---|
| `web_search` | Web search — tries Exa (semantic), then DuckDuckGo, then Brave |
| `web_fetch` | Fetches and extracts readable text from a specific URL |
| Python REPL | Sandboxed Python execution for calculations and data processing |
| `vector_search` | Semantic search over the shared knowledge base and session memory |
| `save_file` / `read_file` / `list_files` | Read/write/list files in the workspace directory |
| `get_session_history` | Reviews past session results |

## Tech Stack

- **LLM**: DeepSeek API (OpenAI-compatible, via `langchain-openai`)
- **Agent Loop**: LangGraph `create_react_agent` (single-agent and multi-agent supervisor)
- **Search**: Exa (semantic) → DuckDuckGo → Brave, in that order, first available wins
- **Vector Store**: Chroma + `sentence-transformers` embeddings (`all-MiniLM-L6-v2`)
- **Code Sandbox**: LangChain `PythonREPLTool` (subprocess-based)
- **Auth**: bcrypt password hashing, JSON-backed user store
- **UI**: Streamlit
- **Storage**: JSON files for sessions/users/costs, Chroma on disk for vectors

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with your API keys:

```
DEEPSEEK_API_KEY=your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
EXA_API_KEY=your-key-here        # optional, improves search quality
BRAVE_API_KEY=your-key-here      # optional, search fallback
```

Run the app:

```bash
streamlit run streamlit_app.py
```

Open `http://localhost:8501` in your browser, register an account, and start chatting.

## Evaluation

Run `python evaluate.py` to test the agent against 7 fixed tasks (4 simple, 3 multi-step). Results are logged with success rate, steps, and timing, and saved to `workspace/evaluation_results.json`.

## Design Decisions

- **LangGraph ReAct** for the agent loop — battle-tested tool-calling and streaming support over a hand-rolled loop
- **DeepSeek** for cost-effective inference via an OpenAI-compatible API
- **Exa → DuckDuckGo → Brave** search cascade — best quality first, free fallback that needs no key, then a paid fallback if configured
- **Streamlit** for the UI — fast to build a chat interface with file upload, auth, and session management without a separate frontend
- **Chroma** for the vector store — zero-config, local, no external services needed
- **JSON files** for sessions/users/costs — zero-config persistence, sufficient for single-instance deployments

## Project Structure

```
├── streamlit_app.py     # Streamlit UI: auth, chat, sessions, uploads, usage stats
├── evaluate.py           # Evaluation runner
├── requirements.txt
├── .env                  # API keys (not committed)
├── .streamlit/config.toml
├── src/
│   ├── agent.py          # ReAct loop orchestration + streaming
│   ├── multi_agent.py    # Supervisor + specialist agents graph
│   ├── llm.py             # DeepSeek (OpenAI-compatible) client
│   ├── tools.py           # Tool implementations and registry
│   ├── memory.py          # Conversation memory carried across follow-ups
│   ├── vector_store.py    # Chroma-backed semantic search + file extraction
│   ├── user_store.py      # Account registration/login + profiles
│   ├── session_store.py   # JSON-based session persistence + tags
│   ├── cost_tracker.py    # Token usage / cost accounting
│   └── config.py          # Configuration (model, API keys)
└── workspace/             # Saved files, sessions, users, vector DB (gitignored)
```

## Limitations

- Single-instance deployment only (JSON file storage, no concurrent-write safety)
- Multi-agent mode does not support follow-up turns — each run starts fresh
- Code execution uses a basic subprocess sandbox (no Docker/E2B isolation)
- DuckDuckGo and free-tier search backends may rate-limit heavy use
