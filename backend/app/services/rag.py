import hashlib
import io
import math
import re
import uuid
from dataclasses import dataclass

from openai import AsyncOpenAI
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, DocumentChunk, DocumentStatus

PROMPT_VERSION = "2026-08-29.1"
MODE_INSTRUCTIONS = {
    "portfolio_summary": "Summarize portfolio positioning, performance drivers, allocations, and material changes.",
    "risk_insight": "Identify and prioritize financial, concentration, liquidity, market, credit, and operational risks. Do not invent risk metrics.",
    "client_communication": "Write a clear, professional client-ready communication. Distinguish facts from interpretation and avoid guarantees.",
    "question": "Answer the user's question directly using only the supplied sources.",
}


@dataclass
class ParsedPage:
    number: int | None
    text: str


def parse_document(data: bytes, content_type: str) -> list[ParsedPage]:
    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(data))
        return [ParsedPage(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
    return [ParsedPage(None, data.decode("utf-8", errors="replace"))]


def split_pages(pages: list[ParsedPage], size: int = 1200, overlap: int = 180) -> list[ParsedPage]:
    output: list[ParsedPage] = []
    for page in pages:
        text = re.sub(r"\s+", " ", page.text).strip()
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                boundary = text.rfind(" ", start + size // 2, end)
                end = boundary if boundary > start else end
            chunk = text[start:end].strip()
            if chunk:
                output.append(ParsedPage(page.number, chunk))
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return output


def _local_embedding(text: str) -> list[float]:
    """Deterministic development embedding; production should configure OpenAI."""
    values = [0.0] * settings.embedding_dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % len(values)
        values[index] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


async def embed(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key:
        return [_local_embedding(text) for text in texts]
    response = await AsyncOpenAI(api_key=settings.openai_api_key).embeddings.create(
        model=settings.openai_embedding_model, input=texts, dimensions=settings.embedding_dimensions
    )
    return [item.embedding for item in response.data]


async def ingest(db: AsyncSession, document: Document, data: bytes) -> None:
    try:
        pages = parse_document(data, document.content_type)
        chunks = split_pages(pages)
        if not chunks:
            raise ValueError("Document contains no extractable text")
        vectors = await embed([chunk.text for chunk in chunks])
        for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            db.add(DocumentChunk(document_id=document.id, ordinal=ordinal, page_number=chunk.number, content=chunk.text, token_count=max(1, len(chunk.text) // 4), embedding=vector))
        document.page_count = len(pages)
        document.status = DocumentStatus.ready
    except Exception as exc:
        document.status = DocumentStatus.failed
        document.error = str(exc)[:2000]
    await db.commit()


async def retrieve(db: AsyncSession, user_id: uuid.UUID, query: str, document_ids: list[uuid.UUID], top_k: int):
    query_vector = (await embed([query]))[0]
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    statement = select(DocumentChunk, Document.filename, distance.label("distance")).join(Document).where(Document.owner_id == user_id, Document.status == DocumentStatus.ready)
    if document_ids:
        statement = statement.where(Document.id.in_(document_ids))
    return (await db.execute(statement.order_by(distance).limit(top_k))).all()


async def generate_answer(query: str, mode: str, contexts: list[tuple]) -> str:
    sources = "\n\n".join(f"[S{i}] {row.filename}, page {row.DocumentChunk.page_number or 'n/a'}\n{row.DocumentChunk.content}" for i, row in enumerate(contexts, 1))
    if not settings.openai_api_key:
        return "Development mode: the most relevant source passages are listed below. Configure FINSIGHT_OPENAI_API_KEY for a synthesized response.\n\n" + "\n\n".join(f"[S{i}] {row.DocumentChunk.content[:500]}" for i, row in enumerate(contexts, 1))
    prompt = f"""You are FinSight, a careful financial research assistant. {MODE_INSTRUCTIONS[mode]}
Use only SOURCES. Cite every factual claim inline as [S1]. If evidence is absent, say so. Never provide personalized investment advice or promise returns.

QUESTION: {query}

SOURCES:
{sources}
"""
    response = await AsyncOpenAI(api_key=settings.openai_api_key).chat.completions.create(model=settings.openai_chat_model, temperature=0.1, messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content or "No answer was generated."

