
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.models import (
    IntentClassification,
    ItineraryPlan,
    ResearchResult,
    ReviewResult,
    WeatherResult,
)


class AgentState(TypedDict, total=False):
    user_query: str
    user_id: str
    thread_id: str

    messages: Annotated[list[AnyMessage], add_messages]
    conversation_history: str
    memory_context: str

    classification: IntentClassification
    research: ResearchResult
    weather: WeatherResult
    itinerary: ItineraryPlan
    review: ReviewResult

    general_answer: str
    final_answer: str

    errors: list[str]
    revision_count: int
