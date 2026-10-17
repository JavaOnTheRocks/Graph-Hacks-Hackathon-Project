
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import MAX_REVISIONS, build_nodes
from app.agent.state import AgentState
from app.config import Settings


def build_graph(settings: Settings, checkpointer):
    nodes = build_nodes(settings)
    workflow = StateGraph(AgentState)

    for name, node in nodes.items():
        workflow.add_node(name, node)

    workflow.add_edge(START, "classify")

    def route_after_classification(
        state: AgentState,
    ) -> Literal["research", "weather", "general"]:
        intent = state["classification"].intent

        if intent == "research" or intent == "trip":
            return "research"
        if intent == "weather":
            return "weather"
        return "general"

    def route_after_research(
        state: AgentState,
    ) -> Literal["weather", "planner", "final"]:
        classification = state["classification"]

        if classification.intent != "trip":
            return "final"
        if classification.needs_weather:
            return "weather"
        return "planner"

    def route_after_weather(
        state: AgentState,
    ) -> Literal["planner", "final"]:
        if state["classification"].intent == "trip":
            return "planner"
        return "final"

    def route_after_review(
        state: AgentState,
    ) -> Literal["planner", "final"]:
        review = state["review"]

        if review.approved:
            return "final"

        if state.get("revision_count", 0) < MAX_REVISIONS:
            return "planner"

        return "final"

    workflow.add_conditional_edges(
        "classify",
        route_after_classification,
        {
            "research": "research",
            "weather": "weather",
            "general": "general",
        },
    )

    workflow.add_conditional_edges(
        "research",
        route_after_research,
        {
            "weather": "weather",
            "planner": "planner",
            "final": "final",
        },
    )

    workflow.add_conditional_edges(
        "weather",
        route_after_weather,
        {
            "planner": "planner",
            "final": "final",
        },
    )

    workflow.add_edge("planner", "reviewer")

    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "planner": "planner",
            "final": "final",
        },
    )

    workflow.add_edge("general", "final")
    workflow.add_edge("final", END)

    return workflow.compile(checkpointer=checkpointer)
