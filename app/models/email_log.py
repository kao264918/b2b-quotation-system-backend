import uuid
import enum
from sqlalchemy import Column, String, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class EmailStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    MOCKED = "mocked"


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    recipient = Column(String, nullable=False, index=True)
    email_type = Column(String, nullable=False)  # e.g. welcome, reset_password, verify, rejection, access_request
    status = Column(Enum(EmailStatus, values_callable=lambda e: [x.name for x in e]), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    provider_message_id = Column(String, nullable=True)
    error_reason = Column(Text, nullable=True)
