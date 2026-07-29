# Autonomous Research & Task Agent

An internship-scoped AI agent project. The agent takes a high-level goal, plans its own steps, uses tools to gather information and take actions, and produces a final deliverable — with minimal human hand-holding.

---

## 1. Problem Statement

Most chatbot projects just answer a single question in one shot. This project builds an **agent**: a system that can take a multi-step goal (e.g. *"Research competitor pricing for product X and summarize into a report"*), break it into subtasks, decide which tools to use, execute them, recover from errors, and produce a final structured output.

---

## 2. Goals

- Understand and implement the **ReAct (Reason + Act)** loop
- Integrate multiple external tools with an LLM via tool/function calling
- Implement short-term memory (scratchpad) and optionally long-term memory (vector store)
- Build basic evaluation to measure agent reliability, not just demo it once
- Ship a usable UI where the agent's reasoning trace is visible

---

## 3. Architecture

```
                ┌─────────────────────┐
                │   User Goal Input     │
                └──────────┬──────────┘
                           │
                  ┌────────▼────────┐
                  │   Planner (LLM)   │
                  │  decides next     │
                  │  step / tool      │
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
 ┌──────▼──────┐   ┌───────▼───────┐   ┌──────▼──────┐
 │  Web Search  │   │ Code Execution │   │ File R/W     │
 │  Tool        │   │ Sandbox        │   │ Tool         │
 └──────┬──────┘   └───────┬───────┘   └──────┬──────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                 ┌─────────▼─────────┐
                 │  Observation /      │
                 │  Memory Update      │
                 └─────────┬─────────┘
                           │
                 loop until goal complete
                           │
                 ┌─────────▼─────────┐
                 │  Final Report /     │
                 │  Output Generator   │
                 └─────────────────────┘
```

### Components

| Component | Responsibility |
|---|---|
| **Planner/Orchestrator** | LLM reasons about the goal and decides the next action (ReAct: Thought → Action → Observation) |
| **Tool Layer** | Executes concrete actions: search, code execution, file I/O, calculator/API calls |
| **Memory** | Short-term scratchpad of steps taken; optional long-term vector store to avoid repeated work |
| **Execution Loop** | Runs the Thought → Action → Observation cycle until a stopping condition is met |
| **Output Generator** | Formats the final result into a clean, structured deliverable (report, summary, table) |

---

## 4. Tools to Implement

Start with 3–4 tools — more isn't better, it just adds failure surface:

1. **Web Search** — Tavily API or SerpAPI, returns snippets + links
2. **Code Execution** — sandboxed Python execution (e.g. E2B, or a locked-down subprocess) for calculations/data processing
3. **File Read/Write** — save intermediate findings and the final report to disk
4. *(Optional)* **Structured API/Calculator** — anything with a clean input/output contract, good for teaching the agent to use structured tools correctly

---

## 5. Build Plan (Staged, Incremental)

| Stage | Milestone | Outcome |
|---|---|---|
| **1** | Single-tool agent (web search only) | Answers one question end-to-end using search |
| **2** | Add a second tool | LLM chooses correct tool based on the task |
| **3** | Multi-step planning | Agent breaks a goal into subtasks and executes sequentially |
| **4** | Memory | Agent avoids repeating searches / redoing completed work |
| **5** | Error handling | Agent detects failed/garbage tool output and retries or adapts |
| **6** | Evaluation | Agent is tested against a fixed task set, with success rate / step count / cost logged |

**Stage 6 is the differentiator.** A demo that works once isn't proof of reliability. A small eval set (10–20 tasks) with logged success rate, average steps to completion, and failure modes turns this into real engineering work rather than a tutorial clone.

---

## 6. Tech Stack

- **LLM**: Claude API (tool use / function calling)
- **Agent framework**: LangGraph (explicit control over the loop) *or* a hand-rolled ReAct loop in plain Python (more learning, still very doable)
- **Search tool**: Tavily or SerpAPI
- **Code sandbox**: E2B or a restricted subprocess
- **UI**: Streamlit or Gradio — show goal input, live reasoning trace, and final output
- **Storage**: local JSON/SQLite for logs; optional vector DB (Chroma/FAISS) for long-term memory

---

## 7. Stretch Goals (pick 1–2 to stand out)

- **Multi-agent setup** — a planner agent delegates subtasks to specialist worker agents
- **Human-in-the-loop approval** — pause for confirmation before risky/irreversible actions
- **Guardrails** — validate/sanity-check tool outputs before the agent acts on them
- **Cost/latency dashboard** — track tokens, API cost, and time per run

---

## 8. Evaluation Plan

Build a small fixed set of 10–20 test goals of varying difficulty (simple single-tool tasks → multi-step tasks requiring 3+ tool calls). For each run, log:

- ✅ / ❌ task success (did it reach a correct, complete answer?)
- Number of steps taken
- Number of tool call failures / retries
- Total tokens and approximate cost
- Time to completion

Summarize these into a small table or chart — this is what separates a "cool demo" from a project with rigor behind it.

---

## 9. Deliverables

- [ ] Working agent with at least 3 integrated tools
- [ ] Streamlit/Gradio UI showing live reasoning trace
- [ ] Evaluation results on a fixed task set (table/chart)
- [ ] README explaining architecture, design decisions, and known limitations
- [ ] (Optional) short demo video/GIF of the agent completing an end-to-end task

---

## 10. Key Tip

Always surface the agent's **reasoning trace** in the UI — not just the final answer. It's the single biggest thing that makes this look like a real agent rather than a wrapped API call, and it's what reviewers and interviewers will remember.
