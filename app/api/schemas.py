
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    thread_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=12000)


class ChatResponse(BaseModel):
    answer: str
    user_id: str
    thread_id: str
    memory_warning: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
