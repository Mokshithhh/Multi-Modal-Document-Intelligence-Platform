import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rate_limit import enforce_rate_limit
from app.core.security import current_user
from app.models import User
from app.schemas import ChatRequest, ChatResponse
from app.services.rag import answer_question, stream_answer

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/completions", response_model=ChatResponse)
async def complete_chat(
    payload: ChatRequest,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_rate_limit(request, f"chat:{user.id}", 60)
    try:
        conversation_id, message_id, answer, citations, latency = await answer_question(
            session, user, payload.message.strip(), payload.conversation_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        logger.exception("Chat completion failed")
        raise HTTPException(status_code=502, detail="Unable to complete document search right now") from None
    return ChatResponse(
        conversation_id=conversation_id,
        message_id=message_id,
        answer=answer,
        citations=citations,
        retrieval_latency_ms=round(latency, 1),
    )


@router.post("/completions/stream")
async def stream_chat_completion(
    payload: ChatRequest,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_rate_limit(request, f"chat:{user.id}", 60)

    async def events():
        try:
            async for event in stream_answer(session, user, payload.message.strip(), payload.conversation_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            await session.rollback()
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        except Exception:
            await session.rollback()
            logger.exception("Streaming chat completion failed")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Unable to complete document search right now'})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
