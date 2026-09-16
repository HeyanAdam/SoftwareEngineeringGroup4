"""AI 对话模块业务逻辑。

当前是「规则式回答」的占位实现: 不依赖任何外部大模型, 保证前后端链路先跑通。
后续接入 RAG / 大模型时, 只需替换 generate_answer() 的实现(建议放到 app/services/rag.py),
路由与前端都不需要改。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.chat import ChatMessage, ChatSession

DEFAULT_TITLE = "新对话"
MAX_HISTORY_FOR_CONTEXT = 6

# 关键词 → 建议, 用于在还没有接入大模型时给出「看起来有用」的回答
KEYWORD_TIPS: list[tuple[tuple[str, ...], str]] = [
    (
        ("数学", "高数", "线代", "概率"),
        "数学建议按「基础 → 强化 → 真题」三阶段推进：\n"
        "1. 基础阶段过一遍教材与基础题，重点是把定义吃透；\n"
        "2. 强化阶段按题型专题突破，每类题型整理错题本；\n"
        "3. 冲刺阶段只做真题与错题，限时训练。\n"
        "每天固定 2 小时给数学，比周末突击 8 小时有效得多。",
    ),
    (
        ("英语", "单词", "阅读", "作文"),
        "英语的核心是「单词 + 真题阅读」：\n"
        "1. 单词每天 30 分钟滚动复习，优先高频词，不要只背新词；\n"
        "2. 阅读用真题精读，每篇做完后逐句翻译，积累长难句；\n"
        "3. 作文从 10 月开始准备模板，每周写 2 篇并找人批改。",
    ),
    (
        ("政治", "马原", "毛中特", "时政"),
        "政治不用开始太早，9 月开始即可：\n"
        "1. 先用选择题打基础，错题反复刷；\n"
        "2. 11 月后集中背大题，跟一位老师的押题资料即可；\n"
        "3. 时政部分考前两周突击。",
    ),
    (
        ("专业课", "408", "统考"),
        "专业课是最容易拉开差距的一门：\n"
        "1. 先按目标院校的参考书过一遍框架，画出知识树；\n"
        "2. 真题至少刷 3 遍，把重复考点标出来；\n"
        "3. 尽量找到目标院校的学长学姐，拿到内部讲义与笔记。",
    ),
    (
        ("计划", "规划", "安排", "时间"),
        "制定计划的三条原则：\n"
        "1. 按周而不是按天排，留出 20% 弹性时间应对意外；\n"
        "2. 每科都要有「可衡量的产出」，例如「做完 20 道积分题」而不是「学数学」；\n"
        "3. 每周复盘一次，完成率低于 70% 就说明计划排得太满。\n"
        "你可以直接在「学习计划」页面建立计划，系统会自动按天拆解任务。",
    ),
    (
        ("焦虑", "心态", "坚持", "放弃", "压力"),
        "备考期的情绪波动很正常，可以试试：\n"
        "1. 把大目标拆成今天能完成的小任务，完成后打勾，获得即时反馈；\n"
        "2. 固定作息与运动时间，睡眠不足会显著拉低效率；\n"
        "3. 少和别人比进度，只和上周的自己比。\n"
        "如果持续失眠或情绪低落，请务必和信任的人聊一聊。",
    ),
    (
        ("院校", "择校", "复试", "调剂"),
        "择校建议按「专业排名 → 报录比 → 复试线 → 地理位置」排序考虑：\n"
        "1. 优先看近三年的报录比与复试线趋势，而不是单看一年；\n"
        "2. 关注是否保护一志愿、复试占比多少；\n"
        "3. 给自己留一个「稳妥档」院校，避免全部冲高。",
    ),
]


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------- 会话 -----------------------------
    def list_sessions(self, user_id: int) -> list[tuple[ChatSession, int]]:
        """返回 (会话, 消息数) 列表, 按最近更新倒序。"""
        count_col = (
            select(func.count(ChatMessage.id))
            .where(ChatMessage.session_id == ChatSession.id)
            .scalar_subquery()
        )
        stmt = (
            select(ChatSession, count_col.label("message_count"))
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )
        return [(row[0], int(row[1] or 0)) for row in self.db.execute(stmt).all()]

    def get_session(self, session_id: int, user_id: int) -> ChatSession:
        session = self.db.get(ChatSession, session_id)
        # 越权访问与不存在返回同样的 404, 不泄露他人会话是否存在
        if session is None or session.user_id != user_id:
            raise NotFoundError("会话不存在")
        return session

    def create_session(self, user_id: int, title: str | None = None) -> ChatSession:
        session = ChatSession(user_id=user_id, title=(title or DEFAULT_TITLE)[:100])
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: int, user_id: int) -> None:
        session = self.get_session(session_id, user_id)
        self.db.delete(session)  # 消息由 cascade 一起删除
        self.db.commit()

    def rename_session(self, session: ChatSession, title: str) -> ChatSession:
        session.title = title[:100]
        self.db.commit()
        self.db.refresh(session)
        return session

    # ----------------------------- 消息 -----------------------------
    def list_messages(self, session_id: int, user_id: int) -> list[ChatMessage]:
        session = self.get_session(session_id, user_id)
        return list(session.messages)

    def send_message(
        self, session_id: int, user_id: int, content: str
    ) -> tuple[ChatMessage, ChatMessage]:
        """写入用户消息, 生成并写入 AI 回答。"""
        content = content.strip()
        if not content:
            raise BadRequestError("消息内容不能为空")

        session = self.get_session(session_id, user_id)

        user_message = ChatMessage(session_id=session.id, role="user", content=content)
        self.db.add(user_message)
        self.db.flush()  # 拿到 id, 同时让后续查询能看到这条消息

        history = [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages[-MAX_HISTORY_FOR_CONTEXT:]
        ]
        answer = generate_answer(content, history)

        assistant_message = ChatMessage(
            session_id=session.id, role="assistant", content=answer
        )
        self.db.add(assistant_message)

        # 首条消息后用提问内容自动命名会话, 便于用户在列表里辨认
        if session.title == DEFAULT_TITLE:
            session.title = content[:20]

        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)
        return user_message, assistant_message


def generate_answer(question: str, history: list[dict[str, str]] | None = None) -> str:
    """生成回答。

    目前的实现是关键词匹配的规则式回答(占位)。接入大模型时替换这里即可,
    入参 history 已经预留(格式: [{"role": "user"/"assistant", "content": "..."}])。
    """
    text = question.lower()

    for keywords, tips in KEYWORD_TIPS:
        if any(word.lower() in text for word in keywords):
            return f"关于「{question.strip()[:20]}」，给你一些参考：\n\n{tips}"

    if history:
        rounds = sum(1 for item in history if item.get("role") == "user")
        if rounds >= 3:
            return (
                "我们已经聊了几轮了。为了给你更具体的建议, 可以补充这些信息:\n"
                "1. 你的目标院校与专业;\n"
                "2. 目前的复习进度(每科到哪一步了);\n"
                "3. 每天能稳定投入的时间。\n"
                "知道这些之后, 我可以帮你把计划排得更贴合实际。"
            )

    return (
        "我是考研 AI 导学助手, 目前支持这些方向的提问:\n\n"
        "- 各科复习方法(数学 / 英语 / 政治 / 专业课)\n"
        "- 学习计划与时间安排\n"
        "- 择校与复试准备\n"
        "- 备考心态与效率问题\n\n"
        "你可以把问题说得更具体一些, 例如「数学基础差, 还有 6 个月怎么安排」。\n"
        "另外, 也可以在「学习计划」页面直接把计划建起来, 系统会自动按天拆解任务。"
    )
