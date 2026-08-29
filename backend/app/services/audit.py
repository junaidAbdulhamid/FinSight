import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


def record_audit(
    db: AsyncSession,
    action: str,
    resource_type: str,
    actor_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(AuditEvent(actor_id=actor_id, action=action, resource_type=resource_type, resource_id=resource_id, detail=detail or {}, ip_address=ip_address))

