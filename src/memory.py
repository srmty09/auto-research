import json
from datetime import datetime


class ConversationMemory:
    def __init__(self, system_prompt: str):
        self.messages = [{"role": "system", "content": system_prompt}]
        self.log = []

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content=None, tool_calls=None):
        msg = {"role": "assistant"}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_message(self, content: str, tool_call_id: str):
        self.messages.append({
            "role": "tool",
            "content": content[:4000],
            "tool_call_id": tool_call_id,
        })

    def get_messages(self):
        return self.messages

    def log_step(self, step: dict):
        step["timestamp"] = datetime.now().isoformat()
        self.log.append(step)

    def get_log(self):
        return self.log

    def save_to_file(self, filepath: str):
        with open(filepath, "w") as f:
            json.dump({"messages": self.messages, "log": self.log}, f, indent=2)
