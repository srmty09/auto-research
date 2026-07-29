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
| **Session Store** | Persists past runs with goals, success status, and logs |
| **Streamlit UI** | Shows live reasoning trace, final answer, and session history |

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

- **LLM**: Groq API (default: `openai/gpt-oss-120b`)
- **Agent Loop**: Hand-rolled ReAct in Python with function calling
- **Search**: DuckDuckGo (free, no API key needed)
- **Code Sandbox**: Restricted subprocess with timeout
- **UI**: Streamlit
- **Storage**: Local JSON files for session persistence

## Setup

```bash
pip install -r requirements.txt

echo "GROQ_API_KEY=your_key_here" > .env

streamlit run app.py
```

## Evaluation

Run `python evaluate.py` to test the agent against 7 fixed tasks (4 simple, 3 multi-step). Results are logged with success rate, steps, and timing.

## Design Decisions

- **Hand-rolled ReAct** over LangGraph for maximum learning value and minimal dependencies
- **Groq over Claude** for fast inference and generous free tier
- **DuckDuckGo over Tavily** — no API key required, works out of the box
- **Function calling** format for structured tool use rather than text-parsed ReAct

## Project Structure

```
├── app.py              # Streamlit UI
├── evaluate.py          # Evaluation runner
├── requirements.txt
├── .env                 # API keys (not committed)
├── project.md           # Original project specification
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
