"""Review task orchestration entry (SSE). Agent graph is wired in M3."""
import json

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from app.models.user import User
from app.schemas.review import ReviewStartRequest


async def stream_review_events(
    request: ReviewStartRequest, current_user: User, db: DBSession
) -> StreamingResponse:
    """M3 接入 LangGraph 全链路后替换实现；当前返回占位事件。"""

    async def gen():
        yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'Agent engine not ready (M3)'}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
