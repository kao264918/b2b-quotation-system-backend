import uuid
from typing import List

from sqlalchemy import String, Boolean, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class QuoteTemplate(Base):
    __tablename__ = "quote_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, default="system") # system, excel
    # Using ARRAY for PostgreSQL, or JSON for compatibility. Let's use JSON for broad compatibility if needed, but ARRAY is fine for Postgres.
    # To be safe and simple, we can use JSON/String, but let's try ARRAY since we are targeting Postgres.
    # However, for simplicity across potential DBs, JSON is safer. I'll use ARRAY(String) as we confirmed Postgres.
    formats: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False) # ['pdf', 'excel']
    
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active")

class InvoiceTemplate(Base):
    __tablename__ = "invoice_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, default="system")
    formats: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active")
