from langchain_openai import ChatOpenAI
from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def get_llm(model=None):
    return ChatOpenAI(
        model=model or DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.7,
    )


def get_model_name(model=None):
    return model or DEEPSEEK_MODEL
