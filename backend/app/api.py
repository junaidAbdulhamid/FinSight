import hashlib
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import AuditEvent, Document, Generation, User
from app.schemas import AuditEventOut, DocumentOut, GenerateRequest, GenerateResponse, RefreshRequest, TokenPair, UserCreate, UserOut
from app.security import current_user, decode_token, hash_password, token_pair, verify_password
from app.services.audit import record_audit
from app.services.rag import PROMPT_VERSION, generate_answer, ingest, retrieve

router = APIRouter(prefix="/api")


@router.post("/auth/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(User.id).where(User.email == payload.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=payload.email.lower(), name=payload.name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    await db.flush()
    record_audit(db, "user.registered", "user", user.id, str(user.id), ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenPair)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    access, refresh = token_pair(user.id)
    record_audit(db, "user.login", "user", user.id, str(user.id))
    await db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(payload.refresh_token, "refresh")
    if not await db.scalar(select(User.id).where(User.id == user_id)):
        raise HTTPException(401, "User no longer exists")
    access, refresh_token = token_pair(user_id)
    return TokenPair(access_token=access, refresh_token=refresh_token)


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user


async def _ingest_document(document_id: uuid.UUID, data: bytes) -> None:
    async with SessionLocal() as db:
        document = await db.get(Document, document_id)
        if document:
            await ingest(db, document, data)


@router.post("/documents", response_model=DocumentOut, status_code=202)
async def upload_document(
    background: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    portfolio: str | None = Form(None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.allowed_upload_types:
        raise HTTPException(415, "Only PDF, plain text, Markdown, and CSV files are supported")
    data = await file.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(413, "File exceeds configured upload limit")
    document = Document(owner_id=user.id, filename=(file.filename or "document")[:255], content_type=content_type, checksum=hashlib.sha256(data).hexdigest(), metadata_={"portfolio": portfolio} if portfolio else {})
    db.add(document)
    await db.flush()
    record_audit(db, "document.uploaded", "document", user.id, str(document.id), {"filename": document.filename, "bytes": len(data)}, request.client.host if request.client else None)
    await db.commit()
    await db.refresh(document)
    background.add_task(_ingest_document, document.id, data)
    return document


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Document).where(Document.owner_id == user.id).order_by(desc(Document.created_at)))).all())


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    document = await db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not document:
        raise HTTPException(404, "Document not found")
    await db.delete(document)
    record_audit(db, "document.deleted", "document", user.id, str(document_id))
    await db.commit()


@router.post("/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    contexts = await retrieve(db, user.id, payload.query, payload.document_ids, payload.top_k)
    if not contexts:
        raise HTTPException(422, "No indexed source material matched this request")
    answer = await generate_answer(payload.query, payload.mode, contexts)
    citations = [{"document_id": row.DocumentChunk.document_id, "filename": row.filename, "chunk_id": row.DocumentChunk.id, "page_number": row.DocumentChunk.page_number, "excerpt": row.DocumentChunk.content[:320], "relevance": round(max(0.0, 1.0 - float(row.distance)), 4)} for row in contexts]
    generation = Generation(user_id=user.id, mode=payload.mode, query=payload.query, answer=answer, citations=citations, model=settings.openai_chat_model if settings.openai_api_key else "local-development", prompt_version=PROMPT_VERSION)
    db.add(generation)
    await db.flush()
    record_audit(db, "generation.created", "generation", user.id, str(generation.id), {"mode": payload.mode, "source_count": len(citations)})
    await db.commit()
    return GenerateResponse(id=generation.id, answer=answer, citations=citations, model=generation.model)


@router.get("/audit", response_model=list[AuditEventOut])
async def audit_log(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(AuditEvent).where(AuditEvent.actor_id == user.id).order_by(desc(AuditEvent.created_at)).limit(100))).all())
