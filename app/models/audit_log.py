import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    """Audit Log for tracking entity changes"""
    __tablename__ = "audit_logs"
    
    __table_args__ = (
        Index('ix_audit_logs_entity', 'entity_type', 'entity_id'),
        Index('ix_audit_logs_timestamp', 'timestamp'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Entity Information
    entity_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "catalog_item"
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    
    # Action Details
    action: Mapped[str] = mapped_column(String, nullable=False)  # "create" | "update" | "inactivate" | "delete"
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Actor (nullable for MVP, can be extended with auth system)
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Optional: detailed changes
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
