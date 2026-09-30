import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.rate_limit import enforce_rate_limit
from app.core.security import current_user
from app.models import Document, DocumentPage, User
from app.schemas import DocumentRead
from app.services.documents import SUPPORTED_MIME_TYPES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_rate_limit(request, f"upload:{user.id}", 20)
    filename = Path(file.filename or "upload").name
    extension = Path(filename).suffix.lower()
    content_type = (file.content_type or "").lower()
    if extension not in ALLOWED_EXTENSIONS or content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Upload a PDF or supported image (PNG, JPEG, TIFF, WebP)")
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"Maximum upload size is {settings.max_upload_bytes // (1024 * 1024)} MB")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File contents do not match a PDF")
    storage_dir = Path(settings.upload_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    document_id = uuid4()
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:180] or "upload"
    storage_path = storage_dir / f"{document_id}_{safe_name}"
    try:
        storage_path.write_bytes(data)
        document = Document(
            id=document_id,
            user_id=user.id,
            filename=filename,
            storage_path=str(storage_path),
            file_size=len(data),
            file_type=content_type,
            status="PENDING",
        )
        session.add(document)
        await session.commit()
        try:
            await request.app.state.redis.lpush("ingestion:queue", str(document_id))
        except Exception:
            document.status = "FAILED"
            document.error_message = "The ingestion queue is unavailable. Re-upload the document when service is restored."
            await session.commit()
            raise HTTPException(status_code=503, detail="The document was stored but could not be queued. Please retry later.") from None
        await request.app.state.redis.incr("metrics:uploads")
        await session.refresh(document)
        return document
    except Exception:
        await session.rollback()
        storage_path.unlink(missing_ok=True)
        logger.exception("Unable to persist document upload for user %s", user.id)
        raise HTTPException(status_code=503, detail="The upload could not be queued. Please retry.") from None


@router.get("", response_model=list[DocumentRead])
async def list_documents(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(500))
    return list(result)


@router.get("/{document_id}/pages/{page_number}")
async def get_document_page(
    document_id: UUID,
    page_number: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    page = await session.scalar(
        select(DocumentPage).join(Document).where(
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
            Document.user_id == user.id,
        )
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Document page not found")
    return {"document_id": document_id, "page_number": page_number, "text_content": page.text_content}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    document = await session.scalar(select(Document).where(Document.id == document_id, Document.user_id == user.id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    Path(document.storage_path).unlink(missing_ok=True)
    await session.delete(document)
    await session.commit()
