from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


class ConversationMemory:
    def __init__(self):
        self.messages = []
        self.log = []

    def get_messages(self):
        return list(self.messages)

    def set_messages(self, messages):
        """Set messages from a LangGraph state."""
        self.messages = list(messages)

    def get_log(self):
        return list(self.log)

    def set_log(self, log):
        self.log = list(log)
