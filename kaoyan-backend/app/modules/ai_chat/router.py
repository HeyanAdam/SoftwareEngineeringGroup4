"""AI 对话模块接口: 会话管理与消息收发。"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.services.chat_service import ChatService
from app.schemas.chat import (
    MessageOut,
    SendMessageRequest,
    SendMessageResponse,
    SessionCreateRequest,
    SessionOut,
    SimpleMessage,
)

router = APIRouter(prefix="/api/ai", tags=["AI对话模块"])


@router.get("/sessions", response_model=list[SessionOut], summary="我的会话列表")
def list_sessions(user: CurrentUser, db: DbSession) -> list[SessionOut]:
    rows = ChatService(db).list_sessions(user.id)
    return [
        SessionOut(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=count,
        )
        for session, count in rows
    ]


@router.post(
    "/sessions",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
    summary="新建会话",
)
def create_session(
    payload: SessionCreateRequest, user: CurrentUser, db: DbSession
) -> SessionOut:
    session = ChatService(db).create_session(user.id, payload.title)
    return SessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.delete("/sessions/{session_id}", response_model=SimpleMessage, summary="删除会话")
def delete_session(session_id: int, user: CurrentUser, db: DbSession) -> SimpleMessage:
    ChatService(db).delete_session(session_id, user.id)
    return SimpleMessage(message="会话已删除")


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[MessageOut],
    summary="会话消息历史",
)
def list_messages(session_id: int, user: CurrentUser, db: DbSession) -> list[MessageOut]:
    messages = ChatService(db).list_messages(session_id, user.id)
    return [MessageOut.model_validate(message) for message in messages]


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    summary="发送消息并获取 AI 回答",
)
def send_message(
    session_id: int, payload: SendMessageRequest, user: CurrentUser, db: DbSession
) -> SendMessageResponse:
    user_message, assistant_message = ChatService(db).send_message(
        session_id, user.id, payload.content
    )
    return SendMessageResponse(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )


@router.get("/ping", summary="模块自检")
def ping() -> dict[str, str]:
    return {"module": "ai_chat", "message": "AI 对话模块运行正常"}
