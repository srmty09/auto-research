from langchain_openai import ChatOpenAI
from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def get_llm(model=None):
    """Return a ChatOpenAI instance configured for the DeepSeek API."""
    return ChatOpenAI(
        model=model or DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.7,
    )


def get_model_name(model=None):
    """Return the resolved model name."""
    return model or DEEPSEEK_MODEL
