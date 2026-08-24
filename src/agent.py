import json
import asyncio
from datetime import datetime
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.exceptions import LangChainException
from langgraph.prebuilt import create_react_agent

from .llm import get_llm, get_model_name
from .tools import get_all_tools
from .cost_tracker import record_usage

DEFAULT_SYSTEM_PROMPT = """You are an autonomous research and task agent. You take a high-level goal from the user and complete it step by step.

RULES:
- Use tools to gather real information — do not make things up
- Break complex goals into smaller subtasks
- Save important findings to files when appropriate
- If a tool fails, try a different approach
- When the goal is fully achieved, provide a clear comprehensive final answer"""


def _extract_log(messages):
    """Extract a step log from a list of LangGraph messages.

    Each tool-use step is a pair of AIMessage (with tool_calls) followed by
    ToolMessage(s). We pair them up into step dicts.
    """
    log = []
    step_num = 0
    i = 0
    while i < len(messages):
        msg = messages[i]
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                step_num += 1
                tool_name = tc["name"]
                try:
                    tool_input = json.loads(tc["args"]) if isinstance(tc["args"], str) else tc["args"]
                except (json.JSONDecodeError, TypeError):
                    tool_input = tc["args"]

                # Find the matching ToolMessage(s) for this tool_call id
                tool_output = ""
                for j in range(i + 1, len(messages)):
                    inner = messages[j]
                    if isinstance(inner, ToolMessage) and inner.tool_call_id == tc["id"]:
                        tool_output = inner.content
                        break

                log.append({
                    "step": step_num,
                    "thought": msg.content or "",
                    "tool": tool_name,
                    "input": tool_input,
                    "output": tool_output[:2000],
                    "timestamp": datetime.now().isoformat(),
                })
        i += 1
    return log


class Agent:
    def __init__(self, model=None, user_id=None, session_id=None, user_context=None, username=None, doc_context=None):
        self.model = model
        self.user_id = user_id
        self.session_id = session_id
        self.user_context = user_context or ""
        self.username = username or ""
        self.doc_context = doc_context or ""
        self._last_state = None
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_tool_calls = 0

    def _build_graph(self):
        llm = get_llm(self.model)
        tools = get_all_tools(self.user_id, session_id=self.session_id)
        system_prompt = DEFAULT_SYSTEM_PROMPT
        if self.user_context:
            system_prompt += f"\n\nUser context: {self.user_context}\nAdapt your responses to match this user's role, interests, and preferences."
        if self.doc_context:
            system_prompt += f"\n\nThe user has uploaded the following document(s) for this chat. Use this knowledge when answering:\n\n{self.doc_context}"
        return create_react_agent(llm, tools, prompt=system_prompt)

    def _record_usage(self, messages, tool_count):
        """Extract token usage from messages and record it."""
        input_tokens = 0
        output_tokens = 0
        for msg in messages:
            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                input_tokens += msg.usage_metadata.get("input_tokens", 0)
                output_tokens += msg.usage_metadata.get("output_tokens", 0)
        if self.username and self.session_id and (input_tokens or output_tokens):
            record_usage(
                session_id=self.session_id,
                user=self.username,
                model=get_model_name(self.model),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_calls=tool_count,
            )

    def run(self, goal: str, max_steps: int = 15, step_callback=None):
        graph = self._build_graph()
        config = {"recursion_limit": max_steps * 2 + 5}
        initial_state = {"messages": [HumanMessage(content=goal)]}

        try:
            state = asyncio.run(graph.ainvoke(initial_state, config=config))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                state = loop.run_until_complete(
                    graph.ainvoke(initial_state, config=config)
                )
            finally:
                loop.close()

        self._last_state = state
        messages = state["messages"]

        # Extract final answer from the last AI message (no tool_calls)
        final_answer = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                final_answer = msg.content
                break

        # Build log from state messages
        log = _extract_log(messages)

        # Record usage
        self._record_usage(messages, len(log))

        # Fire callback for each step
        if step_callback:
            for entry in log:
                step_callback(entry)

        return {
            "success": bool(final_answer),
            "final_answer": final_answer or "Max steps reached without completing the task.",
            "steps": len(log),
            "log": log,
        }

    def continue_run(self, memory, new_message: str, max_steps: int = 10, step_callback=None):
        graph = self._build_graph()
        previous_messages = memory.get_messages()
        messages = previous_messages + [HumanMessage(content=new_message)]

        config = {"recursion_limit": max_steps * 2 + 5}
        initial_state = {"messages": messages}

        try:
            state = asyncio.run(graph.ainvoke(initial_state, config=config))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                state = loop.run_until_complete(
                    graph.ainvoke(initial_state, config=config)
                )
            finally:
                loop.close()

        self._last_state = state
        new_messages = state["messages"]

        # Extract final answer
        final_answer = ""
        for msg in reversed(new_messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                final_answer = msg.content
                break

        # Build log — only include NEW steps (after the previous messages)
        prev_count = len(previous_messages)
        new_log = _extract_log(new_messages[prev_count:])

        # Combine with existing log
        existing_log = memory.get_log()
        start_step = len(existing_log) + 1
        for entry in new_log:
            entry["step"] = start_step
            start_step += 1
        combined_log = existing_log + new_log

        # Record usage
        self._record_usage(new_messages, len(new_log))

        # Fire callback for new steps
        if step_callback:
            for entry in new_log:
                step_callback(entry)

        return {
            "success": bool(final_answer),
            "final_answer": final_answer or "Max steps reached in follow-up.",
            "steps": len(combined_log),
            "log": combined_log,
        }

    async def arun_stream(self, goal: str, max_steps: int = 15) -> AsyncGenerator[dict, None]:
        """Stream agent execution as SSE events via langchain astream_events."""
        graph = self._build_graph()
        config = {"recursion_limit": max_steps * 2 + 5}
        initial_state = {"messages": [HumanMessage(content=goal)]}

        step_num = 0
        pending_tools: dict[str, dict] = {}  # tool_call_id -> partial step
        final_answer = ""

        try:
            async for event in graph.astream_events(initial_state, config=config, version="v2"):
                kind = event.get("event", "")

                # Model is generating tokens
                if kind == "on_chat_model_stream" and not event.get("name", "").endswith("tools"):
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {"type": "thinking", "content": chunk.content}

                # A tool call is starting
                elif kind == "on_tool_start":
                    tool_id = event.get("run_id", "")
                    step_num += 1
                    pending_tools[tool_id] = {
                        "step": step_num,
                        "tool": event.get("name", "unknown"),
                        "input": event.get("data", {}).get("input", {}),
                        "output": "",
                    }
                    yield {
                        "type": "tool_start",
                        "step": step_num,
                        "tool": event.get("name", "unknown"),
                        "input": event.get("data", {}).get("input", {}),
                    }

                # A tool call has finished
                elif kind == "on_tool_end":
                    tool_id = event.get("run_id", "")
                    output = event.get("data", {}).get("output", "")
                    if tool_id in pending_tools:
                        pending_tools[tool_id]["output"] = str(output)[:2000]
                    yield {
                        "type": "tool_end",
                        "step": pending_tools.get(tool_id, {}).get("step", 0),
                        "tool": pending_tools.get(tool_id, {}).get("tool", "unknown"),
                        "output": str(output)[:2000],
                    }

                # Graph finished
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    state = event.get("data", {}).get("output", {})
                    if state and "messages" in state:
                        self._last_state = state
                        for msg in reversed(state["messages"]):
                            if isinstance(msg, AIMessage) and not msg.tool_calls:
                                final_answer = msg.content
                                break

        except LangChainException as e:
            yield {"type": "error", "message": str(e)}
            return

        yield {
            "type": "final_answer",
            "content": final_answer or "Max steps reached without completing the task.",
            "steps": step_num,
        }
