import json
import logging
import re
import time
from collections.abc import AsyncIterator
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import bindparam, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Conversation, Document, DocumentChunk, DocumentPage, Message, User
from app.schemas import Citation
from app.services.documents import embed_texts

logger = logging.getLogger(__name__)


async def _hybrid_search(session: AsyncSession, user_id: UUID, question: str, limit: int = 6) -> list[tuple[DocumentChunk, Document, float]]:
    query_vector = (await embed_texts([question]))[0]
    base = select(DocumentChunk, Document).join(Document).where(
        Document.user_id == user_id,
        Document.status == "COMPLETED",
    )
    vector_rows = (await session.execute(
        base.order_by(DocumentChunk.embedding.cosine_distance(query_vector)).limit(limit)
    )).all()
    query = func.plainto_tsquery("english", bindparam("query", value=question))
    lexical_rows = (await session.execute(
        base.where(DocumentChunk.search_vector.op("@@")(query))
        .order_by(func.ts_rank(DocumentChunk.search_vector, query).desc())
        .limit(limit)
    )).all()
    ranked: dict[UUID, tuple[DocumentChunk, Document, float]] = {}
    for rows in (vector_rows, lexical_rows):
        for rank, (chunk, document) in enumerate(rows, start=1):
            previous = ranked.get(chunk.id)
            score = (previous[2] if previous else 0.0) + 1.0 / (60 + rank)
            ranked[chunk.id] = (chunk, document, score)
    return sorted(ranked.values(), key=lambda entry: entry[2], reverse=True)[:limit]


async def answer_question(session: AsyncSession, user: User, question: str, conversation_id: UUID | None):
    result: dict = {}
    async for event in stream_answer(session, user, question, conversation_id):
        if event["type"] == "delta":
            result["answer"] = result.get("answer", "") + event["content"]
        elif event["type"] == "done":
            result.update(event)
    return (
        UUID(result["conversation_id"]),
        UUID(result["message_id"]),
        result.get("answer", ""),
        [Citation.model_validate(citation) for citation in result.get("citations", [])],
        result["retrieval_latency_ms"],
    )


TOOLS = [
    {"type": "function", "function": {"name": "semantic_search_tool", "description": "Search the current user's indexed document passages for a topic or question.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 8}}, "required": ["query"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "document_lookup_tool", "description": "Look up a user's document by its UUID, optionally on a specific page.", "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}, "page_number": {"type": "integer", "minimum": 1}}, "required": ["document_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "table_analysis_tool", "description": "Find and return table-like rows from the user's indexed document passages.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}}},
]


async def _run_agent_tools(session: AsyncSession, user: User, question: str, evidence: dict[UUID, tuple[DocumentChunk, Document, float]]) -> None:
    if not settings.openai_api_key:
        return
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    messages: list[dict] = [
        {"role": "system", "content": "You are a document research agent. Use the provided tools when they can improve the answer. Never claim that a tool found information unless its result supports that claim. You may make at most one call to each tool."},
        {"role": "user", "content": question},
    ]
    invoked: set[str] = set()
    for _ in range(3):
        completion = await client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0,
            tools=TOOLS,
            tool_choice="auto",
            messages=messages,
        )
        assistant_message = completion.choices[0].message
        calls = assistant_message.tool_calls or []
        if not calls:
            break
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [{
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            } for call in calls],
        })
        for call in calls:
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments)
                if name in invoked:
                    result = {"error": "This tool was already used for this question."}
                elif name == "semantic_search_tool":
                    invoked.add(name)
                    matches = await _hybrid_search(session, user.id, str(arguments["query"])[:12000], min(int(arguments.get("limit", 5)), 8))
                    for chunk, document, score in matches:
                        previous = evidence.get(chunk.id)
                        evidence[chunk.id] = (chunk, document, score + (previous[2] if previous else 0))
                    result = [{"document_id": str(document.id), "filename": document.filename, "page_number": chunk.page_number, "content": chunk.content[:1800]} for chunk, document, _ in matches]
                elif name == "document_lookup_tool":
                    invoked.add(name)
                    document_id = UUID(arguments["document_id"])
                    document = await session.scalar(select(Document).where(Document.id == document_id, Document.user_id == user.id))
                    if document is None:
                        result = {"error": "Document not found in this workspace."}
                    else:
                        page_query = select(DocumentPage).where(DocumentPage.document_id == document.id)
                        if arguments.get("page_number"):
                            page_query = page_query.where(DocumentPage.page_number == int(arguments["page_number"]))
                        pages = (await session.scalars(page_query.order_by(DocumentPage.page_number).limit(4))).all()
                        page_chunks = (await session.scalars(select(DocumentChunk).where(
                            DocumentChunk.document_id == document.id,
                            *([DocumentChunk.page_number == int(arguments["page_number"])] if arguments.get("page_number") else []),
                        ).limit(8))).all()
                        for chunk in page_chunks:
                            evidence[chunk.id] = (chunk, document, 1.0 / 60)
                        result = {"document_id": str(document.id), "filename": document.filename, "status": document.status, "pages": [{"page_number": page.page_number, "text": page.text_content[:2500]} for page in pages]}
                elif name == "table_analysis_tool":
                    invoked.add(name)
                    matches = await _hybrid_search(session, user.id, str(arguments["query"])[:12000], 8)
                    rows = []
                    for chunk, document, score in matches:
                        evidence[chunk.id] = (chunk, document, score + (evidence.get(chunk.id, (chunk, document, 0))[2]))
                        table_lines = [line.strip() for line in chunk.content.splitlines() if "|" in line and len(line.strip()) > 3]
                        if table_lines:
                            rows.append({"filename": document.filename, "page_number": chunk.page_number, "rows": table_lines[:40]})
                    result = rows or {"message": "No table-formatted rows were found in the relevant passages."}
                else:
                    result = {"error": "Unknown tool."}
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                result = {"error": f"Invalid tool arguments: {str(exc)[:200]}"}
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=True)[:12000]})


async def stream_answer(
    session: AsyncSession,
    user: User,
    question: str,
    conversation_id: UUID | None,
) -> AsyncIterator[dict]:
    started = time.perf_counter()
    if conversation_id:
        conversation = await session.scalar(select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        ))
        if conversation is None:
            raise ValueError("Conversation not found")
    else:
        conversation = Conversation(user_id=user.id, title=question[:100])
        session.add(conversation)
        await session.flush()
    matches = await _hybrid_search(session, user.id, question)
    evidence = {chunk.id: (chunk, document, score) for chunk, document, score in matches}
    if matches and settings.openai_api_key:
        await _run_agent_tools(session, user, question, evidence)
    ranked_evidence = sorted(evidence.values(), key=lambda entry: entry[2], reverse=True)[:8]
    citations = [Citation(document_id=document.id, filename=document.filename, page_number=chunk.page_number, snippet_text=chunk.content[:1200]) for chunk, document, _ in ranked_evidence]
    if not ranked_evidence:
        answer = "I couldn't find relevant content in your completed documents. Upload and process a document, then ask again."
        for offset in range(0, len(answer), 72):
            yield {"type": "delta", "content": answer[offset : offset + 72]}
    elif settings.openai_api_key:
        source_text = "\n\n".join(f"[Source {index + 1}: {document.filename}, page {chunk.page_number}]\n{chunk.content}" for index, (chunk, document, _) in enumerate(ranked_evidence))
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        stream = await client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0.1,
            stream=True,
            messages=[
                {"role": "system", "content": "Answer using only the provided document excerpts and relevant tool results. If they do not contain the answer, say so. Cite factual claims using the provided filename and page. Never invent facts or citations."},
                {"role": "user", "content": f"Question: {question}\n\nDocument excerpts:\n{source_text}"},
            ],
        )
        answer_parts: list[str] = []
        async for event in stream:
            content = event.choices[0].delta.content if event.choices else None
            if content:
                answer_parts.append(content)
                yield {"type": "delta", "content": content}
        answer = "".join(answer_parts).strip() or "No answer was returned."
    else:
        answer = "I found these relevant passages in your documents:\n\n" + "\n\n".join(
            f"**{document.filename}, page {chunk.page_number}**\n{chunk.content[:900]}"
            for chunk, document, _ in ranked_evidence[:3]
        ) + "\n\nConfigure `OPENAI_API_KEY` to generate synthesized answers."
        for offset in range(0, len(answer), 72):
            yield {"type": "delta", "content": answer[offset : offset + 72]}
    session.add(Message(conversation_id=conversation.id, role="user", content=question, citations=[]))
    response_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        citations=[citation.model_dump(mode="json") for citation in citations],
    )
    session.add(response_message)
    await session.commit()
    yield {
        "type": "done",
        "conversation_id": str(conversation.id),
        "message_id": str(response_message.id),
        "answer": answer,
        "citations": [citation.model_dump(mode="json") for citation in citations],
        "retrieval_latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }
