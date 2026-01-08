import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    
    # 🔒 Internal Only (frontend must not see this)
    reference_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    
    default_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tax_category: Mapped[str | None] = mapped_column(String, nullable=True) # ID or Code
    
    status: Mapped[str] = mapped_column(String, default="active") # active, inactive
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
