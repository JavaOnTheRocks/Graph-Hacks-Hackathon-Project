
from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import ChatRequest, ChatResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        service="ContinuityOS",
    )


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, request: Request):
    chat_service = request.app.state.chat_service

    try:
        result = chat_service(
            payload.message,
            user_id=payload.user_id,
            thread_id=payload.thread_id,
        )
        return ChatResponse(**result)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        # Log the full exception server-side; don't expose secrets or
        # stack traces to API clients.
        request.app.state.logger.exception("Chat request failed")
        raise HTTPException(
            status_code=500,
            detail="The chat request failed. Check server logs.",
        ) from exc
