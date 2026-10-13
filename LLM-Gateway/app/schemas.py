from typing import Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model: str = "local"

    messages: list[Message] = Field(min_length=1)

    # Cloud fallback must be explicitly approved
    allow_cloud_fallback: bool = False


class ChatResponse(BaseModel):
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int