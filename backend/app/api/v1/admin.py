from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import current_user
from app.models import Document, Message, User

router = APIRouter(prefix="/admin", tags=["observability"])


@router.get("/metrics")
async def metrics(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    statuses = dict((await session.execute(
        select(Document.status, func.count()).where(Document.user_id == user.id).group_by(Document.status)
    )).all())
    message_rows = (await session.execute(
        select(Message.content).join(Message.conversation).where(Message.conversation.has(user_id=user.id), Message.role == "assistant")
    )).scalars().all()
    response_count = len(message_rows)
    failed = statuses.get("FAILED", 0)
    total = sum(statuses.values())
    retrieval_rows = (await session.execute(
        select(Message.citations).join(Message.conversation).where(
            Message.conversation.has(user_id=user.id), Message.role == "assistant"
        )
    )).scalars().all()
    return {
        "documents_total": total,
        "documents_processing": statuses.get("PROCESSING", 0) + statuses.get("PENDING", 0),
        "documents_completed": statuses.get("COMPLETED", 0),
        "documents_failed": failed,
        "error_rate": round(failed / total, 4) if total else 0,
        "messages_total": response_count,
        "estimated_tokens": sum(len(content) // 4 for content in message_rows),
        "retrieval_runs": response_count,
        "citation_count": sum(len(citations or []) for citations in retrieval_rows),
    }
