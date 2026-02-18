from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base

class RegistrationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVATED = "activated"

class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # The spec says "full_name" is required.
    full_name = Column(String, nullable=False)
    # The spec says "company_name" is required.
    company_name = Column(String, nullable=False)
    # The spec says "note" is optional.
    note = Column(String, nullable=True)
    
    status = Column(Enum(RegistrationStatus, values_callable=lambda e: [x.name for x in e]), default=RegistrationStatus.PENDING, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
