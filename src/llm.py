import json
from groq import Groq
from .config import GROQ_API_KEY, GROQ_MODEL


class LLMClient:
    def __init__(self, model=None):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = model or GROQ_MODEL

    def chat(self, messages, tools=None, temperature=0.7):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message
