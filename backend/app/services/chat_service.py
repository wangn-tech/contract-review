"""Chat streaming service: SSE response with context from contract + history."""
import json

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from app.core.config import get_settings
from app.models.session_message import Message, Session
from app.models.user import User
from app.rag.client import get_sf_client
from app.schemas.chat import ChatRequest

settings = get_settings()

SYSTEM_TEMPLATE = """你是高校合同审阅助手，围绕当前合同文件回答用户问题。
规则：只依据合同原文与检索到的制度/法规回答；无法确定时明确说明；不编造条款。"""


def _history_messages(db: DBSession, session_id: int, max_turns: int = 10) -> list[dict]:
    rows = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id.desc())
        .limit(max_turns * 2)
        .all()
    )
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]


def _load_contract_text(db: DBSession, session: Session) -> str:
    from app.models.contract import ContractFile

    if not session.file_id:
        return ""
    contract = db.get(ContractFile, session.file_id)
    if contract is None or not contract.content_path:
        return ""
    try:
        with open(contract.content_path, encoding="utf-8") as f:
            return f.read()[:8000]
    except OSError:
        return ""


async def stream_chat(
    request: ChatRequest, session: Session, current_user: User, db: DBSession
) -> StreamingResponse:
    client = get_sf_client()
    contract_text = _load_contract_text(db, session)
    history = _history_messages(db, session.id)

    # 保存用户消息
    db.add(
        Message(session_id=session.id, role="user", content=request.content or "", parent_id=request.parent_id)
    )
    db.commit()

    system = SYSTEM_TEMPLATE
    if contract_text:
        system += f"\n\n合同原文（节选）：\n{contract_text}"

    full_content: list[str] = []

    async def gen():
        async for delta in client.chat_stream(
            [{"role": "system", "content": system}, *history, {"role": "user", "content": request.content or ""}],
            model=settings.llm_chat_model,
        ):
            full_content.append(delta)
            yield f"data: {json.dumps({'type': 'content', 'content': delta, 'session_id': session.id}, ensure_ascii=False)}\n\n"
        text = "".join(full_content)
        message = Message(session_id=session.id, role="assistant", content=text)
        db.add(message)
        db.commit()
        db.refresh(message)
        yield f"data: {json.dumps({'type': 'done', 'message_id': message.id, 'full_content': text}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
