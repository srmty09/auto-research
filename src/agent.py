import json
import re

import groq

from .llm import LLMClient
from .tools import ToolRegistry
from .memory import ConversationMemory

SYSTEM_PROMPT = """You are an autonomous research and task agent. You take a high-level goal from the user and complete it step by step.

AVAILABLE TOOLS:
- web_search: Search the web for current information. Input: {"query": "search query"}
- web_fetch: Fetch and extract readable text from a specific URL. Input: {"url": "https://example.com"}
- execute_code: Run Python code for calculations or data processing. Input: {"code": "print(1+1)"}
- save_file: Save content to a file. Input: {"filepath": "report.md", "content": "text"}
- read_file: Read content from a file. Input: {"filepath": "report.md"}
- list_files: List all files in the workspace directory. Input: {}
- get_session_history: View your past sessions (goals, success/failure, steps taken). Input: {}

MEMORY:
- You can use get_session_history to review what you accomplished in past runs
- Use save_file to persist important findings you may need later
- Leverage past session history to avoid repeating work

RULES:
- Use tools to gather real information — do not make things up
- Break complex goals into smaller subtasks
- Save important findings to files when appropriate
- If a tool fails, try a different approach
- When the goal is fully achieved, provide a clear comprehensive final answer"""


def parse_action(text):
    lines = text.split("\n")
    action_name = None
    action_input_lines = []
    in_input = False
    for line in lines:
        if line.startswith("Action:") and not in_input:
            action_name = line[len("Action:"):].strip()
        elif line.startswith("Action Input:") and not in_input:
            in_input = True
            rest = line[len("Action Input:"):].strip()
            if rest:
                action_input_lines.append(rest)
        elif in_input:
            if line.startswith("Thought:") or line.startswith("Final") or line.startswith("Observation") or line.startswith("Action:"):
                in_input = False
            else:
                action_input_lines.append(line)
    if action_name and action_input_lines:
        raw = "".join(action_input_lines).strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            args = {}
        return action_name, args
    return None, None


def parse_final(text):
    m = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL)
    return m.group(1).strip() if m else None


class Agent:
    def __init__(self):
        self.llm = LLMClient()
        self.tools = ToolRegistry()

    def run(self, goal: str, max_steps: int = 15, step_callback=None):
        memory = ConversationMemory(SYSTEM_PROMPT)
        memory.add_user_message(goal)
        self._last_memory = memory

        for step in range(1, max_steps + 1):
            try:
                response = self.llm.chat(
                    memory.get_messages(),
                    tools=self.tools.definitions(),
                )
            except groq.BadRequestError:
                response = self.llm.chat(
                    memory.get_messages(),
                    tools=None,
                )

            if response.tool_calls:
                for tc in response.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    result = self.tools.execute(tc.function.name, args)

                    step_info = {
                        "step": step,
                        "thought": response.content or "",
                        "tool": tc.function.name,
                        "input": args,
                        "output": result[:2000],
                    }
                    memory.log_step(step_info)
                    if step_callback:
                        step_callback(step_info)

                    memory.add_assistant_message(
                        content=response.content,
                        tool_calls=[{
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }],
                    )
                    memory.add_tool_message(result, tc.id)
                continue

            content = response.content or ""
            final_answer = parse_final(content)
            if final_answer:
                step_info = {
                    "step": step,
                    "thought": content,
                    "tool": None,
                    "input": None,
                    "output": None,
                }
                memory.log_step(step_info)
                if step_callback:
                    step_callback(step_info)
                memory.add_assistant_message(content=content)
                return {
                    "success": True,
                    "final_answer": final_answer,
                    "steps": step,
                    "log": memory.get_log(),
                }

            action_name, action_args = parse_action(content)
            if action_name:
                result = self.tools.execute(action_name, action_args)
                observation = f"Observation: {result[:3000]}"

                step_info = {
                    "step": step,
                    "thought": content,
                    "tool": action_name,
                    "input": action_args,
                    "output": result[:2000],
                }
                memory.log_step(step_info)
                if step_callback:
                    step_callback(step_info)

                memory.add_assistant_message(content=content)
                memory.add_user_message(observation)
            else:
                step_info = {
                    "step": step,
                    "thought": content,
                    "tool": None,
                    "input": None,
                    "output": None,
                }
                memory.log_step(step_info)
                if step_callback:
                    step_callback(step_info)
                memory.add_assistant_message(content=content)
                return {
                    "success": True,
                    "final_answer": content,
                    "steps": step,
                    "log": memory.get_log(),
                }

        return {
            "success": False,
            "final_answer": "Max steps reached without completing the task.",
            "steps": max_steps,
            "log": memory.get_log(),
        }

    def continue_run(self, memory, new_message: str, max_steps: int = 10, step_callback=None):
        self._last_memory = memory
        memory.add_user_message(new_message)

        start_step = len(memory.get_log()) + 1

        for step in range(start_step, start_step + max_steps):
            try:
                response = self.llm.chat(
                    memory.get_messages(),
                    tools=self.tools.definitions(),
                )
            except groq.BadRequestError:
                response = self.llm.chat(
                    memory.get_messages(),
                    tools=None,
                )

            if response.tool_calls:
                for tc in response.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    result = self.tools.execute(tc.function.name, args)

                    step_info = {
                        "step": step,
                        "thought": response.content or "",
                        "tool": tc.function.name,
                        "input": args,
                        "output": result[:2000],
                    }
                    memory.log_step(step_info)
                    if step_callback:
                        step_callback(step_info)

                    memory.add_assistant_message(
                        content=response.content,
                        tool_calls=[{
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }],
                    )
                    memory.add_tool_message(result, tc.id)
                continue

            content = response.content or ""
            final_answer = parse_final(content)
            if final_answer:
                step_info = {
                    "step": step,
                    "thought": content,
                    "tool": None,
                    "input": None,
                    "output": None,
                }
                memory.log_step(step_info)
                if step_callback:
                    step_callback(step_info)
                memory.add_assistant_message(content=content)
                return {
                    "success": True,
                    "final_answer": final_answer,
                    "steps": step,
                    "log": memory.get_log(),
                }

            action_name, action_args = parse_action(content)
            if action_name:
                result = self.tools.execute(action_name, action_args)
                observation = f"Observation: {result[:3000]}"

                step_info = {
                    "step": step,
                    "thought": content,
                    "tool": action_name,
                    "input": action_args,
                    "output": result[:2000],
                }
                memory.log_step(step_info)
                if step_callback:
                    step_callback(step_info)

                memory.add_assistant_message(content=content)
                memory.add_user_message(observation)
            else:
                step_info = {
                    "step": step,
                    "thought": content,
                    "tool": None,
                    "input": None,
                    "output": None,
                }
                memory.log_step(step_info)
                if step_callback:
                    step_callback(step_info)
                memory.add_assistant_message(content=content)
                return {
                    "success": True,
                    "final_answer": content,
                    "steps": step,
                    "log": memory.get_log(),
                }

        return {
            "success": False,
            "final_answer": "Max steps reached in follow-up.",
            "steps": start_step + max_steps - 1,
            "log": memory.get_log(),
        }
