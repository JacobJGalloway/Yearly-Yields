from typing import Any

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
    type: str                           # chart | table | link | clarifying_question | text
    content: str | None = None         # text body, link description, or clarifying question
    url: str | None = None             # link only
    title: str | None = None           # chart / table heading
    chart_type: str | None = None      # bar_grouped | bar_stacked | line_multi | bar_single
    x_labels: list[str] | None = None
    series: list[dict[str, Any]] | None = None
    y_axis_label: str | None = None
    columns: list[str] | None = None   # table only
    rows: list[list[Any]] | None = None
    options: list[str] | None = None   # clarifying_question suggested answers


@router.post("/", response_model=ChatResponse)
async def dashboard_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    result = await run_chat(
        message=payload.message,
        history=[m.model_dump() for m in payload.history],
        db=db,
        owner_id=str(current_user.id),
    )
    return ChatResponse(**result)
