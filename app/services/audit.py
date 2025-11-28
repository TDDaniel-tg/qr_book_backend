from __future__ import annotations

from typing import Any, Optional

from ..extensions import db
from ..models import AuditAction, AuditLog


def record_action(*, user_id: Optional[int], action: AuditAction, description: str, payload: dict[str, Any] | None = None) -> AuditLog:
    log = AuditLog(actor_id=user_id, action=action, description=description, payload=payload)
    db.session.add(log)
    db.session.commit()
    return log


def list_logs(*, limit: int = 100) -> list[AuditLog]:
    return list(
        db.session.execute(
            db.select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        ).scalars()
    )
