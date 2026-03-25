from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.catalog import CatalogItem
from app.models.promotion import Promotion
from app.services.promotion_pricing import (
    PromotionValidationError,
    calculate_promotion_discount,
    get_promotion_runtime_status,
    validate_promotion_for_quote,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[CatalogItem.__table__, Promotion.__table__])
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine, tables=[Promotion.__table__, CatalogItem.__table__])


def _build_promotion(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": "promo-1",
        "promotion_code": "PROMO-2603-001",
        "promotion_name": "Spring Promo",
        "type": "percentage",
        "discount_value": Decimal("10.00"),
        "minimum_order_amount": Decimal("500.00"),
        "scope": "all_products",
        "scope_category": None,
        "is_active": True,
        "start_at": now - timedelta(days=1),
        "end_at": now + timedelta(days=1),
    }
    values.update(overrides)
    return Promotion(**values)


def test_get_promotion_runtime_status_active():
    promotion = _build_promotion()
    assert get_promotion_runtime_status(promotion) == "active"


def test_get_promotion_runtime_status_scheduled():
    promotion = _build_promotion(start_at=datetime.now(timezone.utc) + timedelta(days=1))
    assert get_promotion_runtime_status(promotion) == "scheduled"


def test_calculate_fixed_amount_promotion_caps_by_subtotal():
    assert calculate_promotion_discount(Decimal("800.00"), "fixed_amount", Decimal("1000.00")) == Decimal("800.00")


def test_validate_promotion_rejects_below_minimum_order(db_session):
    promotion = _build_promotion()
    with pytest.raises(PromotionValidationError) as exc:
        validate_promotion_for_quote(
            db_session,
            promotion,
            [],
            Decimal("100.00"),
        )
    assert exc.value.code == "PROMOTION_MIN_ORDER_NOT_MET"


def test_validate_promotion_accepts_matching_category_scope(db_session):
    catalog_item = CatalogItem(
        id="catalog-1",
        item_no="P-0001",
        name="Sensor",
        type="product",
        unit="pcs",
        reference_cost=Decimal("50.00"),
        default_price=Decimal("100.00"),
        category="Sensors",
        status="active",
    )
    db_session.add(catalog_item)
    db_session.commit()

    promotion = _build_promotion(scope="category", scope_category="Sensors")
    quote_item = SimpleNamespace(catalog_item_id="catalog-1")
    validate_promotion_for_quote(db_session, promotion, [quote_item], Decimal("1000.00"))
