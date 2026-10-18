
from fastapi import APIRouter, HTTPException, Query, Request

from app.api.schemas import ChatRequest, ChatResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        service="Personal Assistant",
    )


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, request: Request):
    chat_service = request.app.state.chat_service
    conversation_store = request.app.state.conversation_store

    try:
        # Create the conversation if it does not already exist.
        conversation_store.ensure_conversation(
            user_id=payload.user_id,
            thread_id=payload.thread_id,
            first_message=payload.message,
        )

        # Persist the user's message before generating the response.
        conversation_store.add_message(
            user_id=payload.user_id,
            thread_id=payload.thread_id,
            role="user",
            content=payload.message,
        )

        result = chat_service(
            payload.message,
            user_id=payload.user_id,
            thread_id=payload.thread_id,
        )

        # Persist the assistant's response.
        conversation_store.add_message(
            user_id=payload.user_id,
            thread_id=payload.thread_id,
            role="assistant",
            content=result["answer"],
        )

        return ChatResponse(**result)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        request.app.state.logger.exception(
            "Chat request failed"
        )
        raise HTTPException(
            status_code=500,
            detail="The chat request failed. Check server logs.",
        ) from exc


@router.get("/conversations")
def list_conversations(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
):
    try:
        conversations = (
            request.app.state.conversation_store
            .list_conversations(user_id)
        )
        return {"conversations": conversations}

    except Exception as exc:
        request.app.state.logger.exception(
            "Failed to list conversations"
        )
        raise HTTPException(
            status_code=500,
            detail="Could not load conversation history.",
        ) from exc


@router.get("/conversations/{thread_id}")
def get_conversation(
    thread_id: str,
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
):
    if not thread_id or len(thread_id) > 128:
        raise HTTPException(
            status_code=400,
            detail="Invalid thread_id.",
        )

    try:
        store = request.app.state.conversation_store

        conversations = store.list_conversations(user_id)
        conversation = next(
            (
                item
                for item in conversations
                if item["thread_id"] == thread_id
            ),
            None,
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        messages = store.get_messages(user_id, thread_id)

        return {
            "conversation": conversation,
            "messages": messages,
        }

    except HTTPException:
        raise

    except Exception as exc:
        request.app.state.logger.exception(
            "Failed to retrieve conversation"
        )
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve conversation history.",
        ) from exc


@router.delete("/conversations/{thread_id}")
def delete_conversation(
    thread_id: str,
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
):
    if not thread_id or len(thread_id) > 128:
        raise HTTPException(
            status_code=400,
            detail="Invalid thread_id.",
        )

    try:
        deleted = (
            request.app.state.conversation_store
            .delete_conversation(user_id, thread_id)
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        return {
            "message": "Conversation history deleted.",
            "thread_id": thread_id,
        }

    except HTTPException:
        raise

    except Exception as exc:
        request.app.state.logger.exception(
            "Failed to delete conversation"
        )
        raise HTTPException(
            status_code=500,
            detail="Could not delete conversation history.",
        ) from exc
