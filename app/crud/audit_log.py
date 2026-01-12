from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: Optional[str] = None,
    changes: Optional[dict] = None
) -> AuditLog:
    """
    Log an action to audit_logs table.
    
    Args:
        db: Database session
        entity_type: Type of entity (e.g., "catalog_item")
        entity_id: ID of the entity
        action: Action performed ("create" | "update" | "inactivate" | "delete")
        actor: Optional user/actor identifier (for future auth integration)
        changes: Optional detailed changes dict
    
    Returns:
        Created AuditLog instance
    """
    log_entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        changes=changes
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
