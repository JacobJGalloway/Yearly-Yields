from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chat import run_chat
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    response: str


@router.post("/", response_model=ChatResponse)
async def dashboard_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    response = await run_chat(
        message=payload.message,
        history=[m.model_dump() for m in payload.history],
        db=db,
        owner_id=str(current_user.id),
    )
    return ChatResponse(response=response)
