"""AI 对话模块的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100, description="留空则用默认标题")


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str = Field(description="user = 学生提问, assistant = AI 回答")
    content: str
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000, description="提问内容")


class SendMessageResponse(BaseModel):
    """一次问答返回两条消息, 前端可直接追加到列表末尾。"""

    user_message: MessageOut
    assistant_message: MessageOut


class SimpleMessage(BaseModel):
    message: str = "ok"
