
from langchain_openai import ChatOpenAI

from app.config import Settings


def create_llm(settings: Settings) -> ChatOpenAI:
    """Create the shared OpenAI chat model for ContinuityOS."""
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
        timeout=45,
        max_retries=2,
    )
