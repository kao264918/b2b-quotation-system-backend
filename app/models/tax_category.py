import uuid
from decimal import Decimal

from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class TaxCategory(Base):
    __tablename__ = "tax_categories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True) # e.g., 'standard'
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False) # e.g., 0.0500
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    
    status: Mapped[str] = mapped_column(String, default="active") # active, inactive
