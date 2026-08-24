import json
import asyncio
from datetime import datetime
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from .llm import get_llm
from .tools import (
    web_search, web_fetch, make_vector_search,
    execute_code, make_save_file, make_read_file,
    get_session_history,
)


# ── Agent State ────────────────────────────────────────────────────────────

from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class MultiAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next: str  
    task_log: list  

SPECIALISTS = {
    "researcher": {
        "prompt": (
            "You are a research specialist. You search the web, fetch pages, "
            "and search the knowledge base to find accurate, current information. "
            "Provide thorough, well-sourced findings. Always cite URLs when available."
        ),
        "tools": [web_search, web_fetch, get_session_history],
    },
    "writer": {
        "prompt": (
            "You are a writing specialist. You take research findings and produce "
            "clear, well-structured documents. You can also read existing files. "
            "Write in a professional, concise style. Use markdown formatting."
        ),
        "tools": [],
    },
    "coder": {
        "prompt": (
            "You are a coding specialist. You write and execute Python code for "
            "calculations, data analysis, simulations, and automation. "
            "Always verify your results. Use print() to show output."
        ),
        "tools": [execute_code, get_session_history],
    },
}


def _build_specialist(name: str, user_id=None):
    """Build a specialist agent as a LangGraph sub-graph."""
    spec = SPECIALISTS[name]
    llm = get_llm()

    # Build user-scoped tools for writer
    tools = list(spec["tools"])
    if name == "writer":
        tools = [
            web_search, web_fetch, make_vector_search(),
            make_save_file(user_id), make_read_file(user_id),
            get_session_history,
        ]
    elif name == "researcher":
        tools = [
            web_search, web_fetch, make_vector_search(),
            get_session_history,
        ]

    return create_react_agent(llm, tools, prompt=spec["prompt"])


SUPERVISOR_PROMPT = """You are a supervisor coordinating a team of specialist agents to complete the user's task.

Your team:
- **researcher**: Searches the web and knowledge base for information
- **writer**: Writes and saves documents and reports
- **coder**: Executes Python code for calculations and data processing

Based on the user's goal, decide which specialist should work next.
When the task is fully complete, respond with FINISH.

Rules:
- Start with the researcher for information-gathering tasks
- Use the coder for calculations or data processing
- Use the writer when you need to create a document or report
- You can call multiple specialists in sequence
- When all work is done, say FINISH with the final summary"""


def supervisor_node(state: MultiAgentState) -> dict:
    """Ask the supervisor LLM which specialist to use next."""
    llm = get_llm()

    messages = state["messages"]
    task_log = state.get("task_log", [])
    log_summary = "\n".join(
        f"  - {entry['agent']}: {entry['summary'][:100]}"
        for entry in task_log
    ) if task_log else "  (no work done yet)"

    prompt = [
        SystemMessage(content=SUPERVISOR_PROMPT),
        HumanMessage(content=(
            f"User goal: {messages[-1].content}\n\n"
            f"What has been done so far:\n{log_summary}\n\n"
            f"Which specialist should work next? Or say FINISH if the task is complete."
        )),
    ]

    response = llm.invoke(prompt)
    choice = response.content.strip().upper()

    if "FINISH" in choice:
        return {"next": "FINISH"}
    elif "RESEARCH" in choice:
        return {"next": "researcher"}
    elif "WRIT" in choice:
        return {"next": "writer"}
    elif "COD" in choice or "EXECUT" in choice or "CALCULAT" in choice:
        return {"next": "coder"}
    else:
        return {"next": "FINISH"}


def specialist_node(name: str):
    """Create a node function for a specialist agent."""
    def node(state: MultiAgentState) -> dict:
        llm = get_llm()
        spec = SPECIALISTS[name]
        tools = [web_search, web_fetch, make_vector_search(), execute_code,
                 make_save_file(1), make_read_file(1), get_session_history]

        graph = create_react_agent(llm, tools, prompt=spec["prompt"])

        goal = state["messages"][-1].content
        initial = {"messages": [HumanMessage(content=goal)]}

        try:
            result = asyncio.run(graph.ainvoke(initial, config={"recursion_limit": 10}))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(graph.ainvoke(initial, config={"recursion_limit": 10}))
            finally:
                loop.close()

        # Extract the specialist's output
        output = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                output = msg.content
                break

        task_log = state.get("task_log", [])
        task_log.append({
            "agent": name,
            "summary": output[:200],
            "timestamp": datetime.now().isoformat(),
        })

        return {
            "messages": [AIMessage(content=f"[{name.upper()}] {output}")],
            "task_log": task_log,
        }

    return node


def final_node(state: MultiAgentState) -> dict:
    """Compile the final answer from all specialist outputs."""
    llm = get_llm()
    messages = state["messages"]
    task_log = state.get("task_log", [])

    specialist_outputs = [
        msg.content for msg in messages
        if isinstance(msg, AIMessage) and msg.content.startswith("[")
    ]

    prompt = [
        SystemMessage(content=(
            "You are compiling a final answer from the outputs of multiple specialist agents. "
            "Combine their findings into a clear, comprehensive, well-structured response. "
            "Use markdown formatting. Be concise but thorough."
        )),
        HumanMessage(content=(
            f"Original goal: {messages[0].content}\n\n"
            f"Specialist outputs:\n" +
            "\n\n".join(specialist_outputs) +
            f"\n\nProvide the final compiled answer."
        )),
    ]

    response = llm.invoke(prompt)

    return {
        "messages": [AIMessage(content=response.content)],
        "task_log": task_log,
    }


# ── Build the Graph ────────────────────────────────────────────────────────

def build_multi_agent_graph():
    """Build the multi-agent supervisor graph."""
    workflow = StateGraph(MultiAgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("researcher", specialist_node("researcher"))
    workflow.add_node("writer", specialist_node("writer"))
    workflow.add_node("coder", specialist_node("coder"))
    workflow.add_node("final", final_node)

    # Supervisor routes to specialists or FINISH
    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state["next"],
        {
            "researcher": "researcher",
            "writer": "writer",
            "coder": "coder",
            "FINISH": "final",
        },
    )

    # Specialists always return to supervisor
    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("writer", "supervisor")
    workflow.add_edge("coder", "supervisor")
    workflow.add_edge("final", END)

    return workflow.compile()


# ── Public API ─────────────────────────────────────────────────────────────

class MultiAgent:
    """Multi-agent orchestrator with supervisor pattern."""

    def __init__(self, user_id=None):
        self.user_id = user_id
        self._graph = None
        self._last_state = None

    def _build_graph(self):
        if self._graph is None:
            self._graph = build_multi_agent_graph()
        return self._graph

    def run(self, goal: str, max_rounds: int = 5):
        graph = self._build_graph()
        config = {"recursion_limit": max_rounds * 4 + 5}
        initial = {
            "messages": [HumanMessage(content=goal)],
            "task_log": [],
        }

        try:
            state = asyncio.run(graph.ainvoke(initial, config=config))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                state = loop.run_until_complete(graph.ainvoke(initial, config=config))
            finally:
                loop.close()

        self._last_state = state

        # Extract final answer
        final_answer = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and "FINISH" not in msg.content[:10]:
                final_answer = msg.content
                break

        task_log = state.get("task_log", [])

        return {
            "success": bool(final_answer),
            "final_answer": final_answer or "Multi-agent task did not complete.",
            "steps": len(task_log),
            "log": [
                {
                    "step": i + 1,
                    "thought": entry.get("summary", ""),
                    "tool": entry["agent"],
                    "input": None,
                    "output": entry.get("summary", ""),
                    "timestamp": entry.get("timestamp", ""),
                }
                for i, entry in enumerate(task_log)
            ],
            "agents_used": [e["agent"] for e in task_log],
        }
