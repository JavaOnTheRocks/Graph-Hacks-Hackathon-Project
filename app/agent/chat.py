
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.state import AgentState
from app.memory.long_term import LongTermMemory
from app.memory.short_term import format_conversation_history


def create_chat_service(graph, long_term_memory: LongTermMemory):
    def chat(
        user_query: str,
        *,
        user_id: str,
        thread_id: str,
    ) -> dict:
        if not user_query.strip():
            raise ValueError("user_query cannot be empty.")
        if not user_id.strip():
            raise ValueError("user_id is required.")
        if not thread_id.strip():
            raise ValueError("thread_id is required.")

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 30,
            "metadata": {
                "app": "Personal Assistant",
                "thread_id": thread_id,
                # Avoid putting sensitive user data in trace metadata.
            },
            "tags": ["personal-assistant", "chat"],
        }

        # 1. Read recent checkpointed conversation history.
        history = ""
        try:
            snapshot = graph.get_state(config)
            messages = snapshot.values.get("messages", [])
            history = format_conversation_history(messages)
        except Exception:
            # A new thread may not have a checkpoint yet.
            history = ""

        # 2. Retrieve the user's relevant long-term memories.
        memory_context = ""
        try:
            memories = long_term_memory.retrieve_all(
                user_query,
                user_id=user_id,
            )
            memory_context = long_term_memory.format_context(memories)
        except Exception:
            # Memory failures should not necessarily prevent a chat reply.
            memory_context = "Long-term memory retrieval was unavailable."

        # 3. Run the LangGraph workflow.
        initial_state: AgentState = {
            "user_query": user_query,
            "user_id": user_id,
            "thread_id": thread_id,
            "messages": [HumanMessage(content=user_query)],
            "conversation_history": history,
            "memory_context": memory_context,
            "errors": [],
            "revision_count": 0,
        }

        result = graph.invoke(initial_state, config=config)

        answer = (
            result.get("final_answer")
            or result.get("general_answer")
            or "No final answer was generated."
        )

        # 4. Append the assistant reply to checkpointed messages.
        # The user message was already added during graph.invoke().
        graph.update_state(
            config,
            {"messages": [AIMessage(content=answer)]},
        )

        # 5. Store the completed interaction in long-term episodic memory.
        memory_warning = None
        try:
            long_term_memory.add(
                "episodic",
                f"User request: {user_query}\nAssistant response: {answer}",
                user_id=user_id,
            )
        except Exception as exc:
            memory_warning = f"Episodic memory storage failed: {exc}"

        # 6. Capture explicit user preferences or workflows.
        try:
            long_term_memory.capture_explicit_memory(
                user_query,
                user_id=user_id,
            )
        except Exception as exc:
            memory_warning = (
                f"{memory_warning or ''} "
                f"Explicit memory capture failed: {exc}"
            ).strip()

        return {
            "answer": answer,
            "user_id": user_id,
            "thread_id": thread_id,
            "memory_warning": memory_warning,
        }

    return chat
