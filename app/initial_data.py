import logging
import random
from decimal import Decimal

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models, crud, schemas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db(db: Session) -> None:
    # 1. Units
    # Model: id, label, status
    units = ["pcs", "set", "box", "hr", "trip", "m", "m2"]
    for u_label in units:
        existing = db.query(models.Unit).filter(models.Unit.label == u_label).first()
        if not existing:
            db_obj = models.Unit(
                label=u_label,
                status="active"
            )
            db.add(db_obj)
            logger.info(f"Created Unit: {u_label}")
    db.commit()

    # 2. Tax Categories
    # Model: id, name, code, rate, description, status
    taxes = [
        {"code": "TAX_5", "name": "Value Added Tax (5%)", "rate": 0.05},
        {"code": "ZERO", "name": "Zero Rated (0%)", "rate": 0.00},
        {"code": "EXEMPT", "name": "Tax Exempt", "rate": 0.00},
    ]
    for t in taxes:
        existing = db.query(models.TaxCategory).filter(models.TaxCategory.code == t["code"]).first()
        if not existing:
            db_obj = models.TaxCategory(
                code=t["code"],
                name=t["name"],
                rate=Decimal(str(t["rate"])),
                status="active"
            )
            db.add(db_obj)
            logger.info(f"Created TaxCategory: {t['code']}")
    db.commit()

    # 3. Catalog Items (Test Data)
    # Check if we have items
    if db.query(models.CatalogItem).count() == 0:
        items = [
            {
                "name": "Consulting Service",
                "type": "service",
                "unit": "hr",
                "reference_cost": 500,
                "default_price": 1000,
                "description": "Standard consulting service"
            },
            {
                "name": "Standard Widget",
                "type": "product",
                "unit": "pcs",
                "reference_cost": 50,
                "default_price": 120,
                "description": "A high quality widget"
            },
            {
                "name": "Construction Output",
                "type": "output",
                "unit": "set",
                "reference_cost": 2000,
                "default_price": 5000,
                "description": "Final output delivery"
            }
        ]
        
        # We need to use CRUD or manually creating to handle item_no generation?
        # Using CRUD is safer if logic is complex (like item_no).
        # But CRUD requires schemas. Let's try to mimic simplistic logic or use CRUD.
        # We'll use crud.catalog.create_with_item_no if possible, but it requires Schema.
        
        for item_data in items:
            try:
                item_in = schemas.CatalogItemCreate(
                    name=item_data["name"],
                    type=item_data["type"],
                    unit=item_data["unit"],
                    reference_cost=Decimal(item_data["reference_cost"]),
                    default_price=Decimal(item_data["default_price"]),
                    description=item_data["description"]
                )
                crud.catalog.create_with_item_no(db, obj_in=item_in)
                logger.info(f"Created Item: {item_data['name']}")
            except Exception as e:
                logger.error(f"Failed to create item {item_data['name']}: {e}")
    else:
        logger.info("Catalog Items already exist. Skipping.")

    # 4. Customers (Test Data)
    if db.query(models.Customer).count() == 0:
        # Note: Model requires address/city/country, though schema might treat as optional.
        # We provide full dummy data.
        customer_in = schemas.CustomerCreate(
            company_name="Acme Corp Test",
            tax_id="12345678",
            contact_name="John Doe",
            contact_email="john@acme.test",
            contact_phone="0912345678",
            address_line1="123 Test St",
            city="Taipei",
            country="Taiwan",
            status="active"
        )
        try:
            crud.customer.create(db, obj_in=customer_in)
            logger.info("Created Customer: Acme Corp Test")
        except Exception as e:
            logger.error(f"Failed to create customer: {e}")
    else:
        logger.info("Customers already exist. Skipping.")

def main() -> None:
    logger.info("Creating initial data")
    try:
        db = SessionLocal()
        init_db(db)
        logger.info("Initial data created")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    main()
