import asyncio
import hashlib
import logging
import math
import re
from pathlib import Path
from uuid import UUID

import fitz
import pytesseract
from openai import AsyncOpenAI
from PIL import Image
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionFactory
from app.models import Document, DocumentChunk, DocumentPage

logger = logging.getLogger(__name__)
SUPPORTED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff", "image/webp"}
OCR_CONFIG = "--psm 6"


def _extract_pages(path: Path, mime_type: str) -> list[str]:
    if mime_type == "application/pdf":
        pages: list[str] = []
        with fitz.open(path) as pdf:
            for page in pdf:
                content = page.get_text("text").strip()
                if len(content) < 30:
                    try:
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        import io

                        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                        content = pytesseract.image_to_string(image, config=OCR_CONFIG).strip()
                    except pytesseract.TesseractNotFoundError:
                        logger.warning("Tesseract is unavailable; scanned page has no OCR text: %s", path.name)
                pages.append(content)
        return pages
    try:
        return [pytesseract.image_to_string(Image.open(path), config=OCR_CONFIG).strip()]
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError("Tesseract OCR is required to process image uploads") from exc


def _split_chunks(content: str, target_chars: int = 3000, overlap_chars: int = 512) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", content)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current) + len(paragraph) + 2 > target_chars and current:
            chunks.append(current)
            current = current[-overlap_chars:] + "\n\n" + paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
        while len(current) > target_chars * 1.5:
            chunks.append(current[:target_chars])
            current = current[target_chars - overlap_chars :]
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _has_searchable_text(content: str) -> bool:
    return bool(re.search(r"[A-Za-z]{3,}|\d{3,}", content))


def _local_embedding(content: str) -> list[float]:
    vector = [0.0] * 1536
    for term in re.findall(r"[a-z0-9]{2,}", content.lower()):
        digest = hashlib.blake2b(term.encode(), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % len(vector)
        vector[index] += 1.0
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


async def embed_texts(contents: list[str]) -> list[list[float]]:
    if settings.openai_api_key:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(model=settings.openai_embedding_model, input=contents)
        return [item.embedding for item in response.data]
    return [_local_embedding(content) for content in contents]


async def ingest_document(document_id: UUID) -> None:
    async with SessionFactory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return
        document.status = "PROCESSING"
        await session.commit()
        try:
            pages = await asyncio.to_thread(_extract_pages, Path(document.storage_path), document.file_type)
            chunks_to_store: list[tuple[int, int, str]] = []
            await session.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            for page_number, page_content in enumerate(pages, start=1):
                session.add(DocumentPage(document_id=document_id, page_number=page_number, text_content=page_content))
                chunks_to_store.extend((page_number, index, chunk) for index, chunk in enumerate(_split_chunks(page_content)) if chunk.strip())
            if not chunks_to_store or (
                document.file_type in {"image/png", "image/jpeg", "image/tiff", "image/webp"}
                and not any(_has_searchable_text(page) for page in pages)
            ):
                raise ValueError("No readable text was extracted. Try a clearer scan or a text-based PDF.")
            if chunks_to_store:
                vectors: list[list[float]] = []
                for start in range(0, len(chunks_to_store), 64):
                    batch = chunks_to_store[start : start + 64]
                    vectors.extend(await embed_texts([item[2] for item in batch]))
                for (page_number, chunk_index, content), vector in zip(chunks_to_store, vectors, strict=True):
                    session.add(DocumentChunk(
                        document_id=document_id,
                        page_number=page_number,
                        chunk_index=chunk_index,
                        content=content,
                        embedding=vector,
                        metadata_json={"filename": document.filename},
                    ))
                await session.flush()
                await session.execute(text("UPDATE document_chunks SET search_vector = to_tsvector('english', content) WHERE document_id = :id"), {"id": document_id})
            document.status = "COMPLETED"
            document.error_message = None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            document = await session.get(Document, document_id)
            if document:
                document.status = "FAILED"
                document.error_message = str(exc)[:2000]
                await session.commit()
            logger.exception("Document ingestion failed for %s", document_id)
