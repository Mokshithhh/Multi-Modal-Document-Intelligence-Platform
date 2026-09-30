from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(String(1024))
    file_size: Mapped[int] = mapped_column(Integer)
    file_type: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (Index("ix_document_pages_document_page", "document_id", "page_number", unique=True),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text_content: Mapped[str] = mapped_column(Text, default="")
    document: Mapped[Document] = relationship(back_populates="pages")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_document_chunks_content_fts", "search_vector", postgresql_using="gin"),
        Index("ix_document_chunks_document_page", "document_id", "page_number"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)
    document: Mapped[Document] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
