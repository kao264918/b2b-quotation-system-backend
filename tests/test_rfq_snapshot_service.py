
"""
Unit tests for Catalog to RFQ Snapshot Service
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from app.models.catalog import CatalogItem
from app.services.catalog_to_rfq_snapshot import (
    calculate_area_unit,
    create_rfq_item_from_catalog,
    update_rfq_item_with_recalculation
)
from app.models.rfq import RFQItem

def test_calculate_area_unit_standard():
    """Test standard area unit calculation"""
    # 90cm x 100cm = 9000 sq cm / 900 = 10 units
    assert calculate_area_unit(Decimal("90"), Decimal("100")) == Decimal("10")

def test_calculate_area_unit_rounding():
    """Test area unit calculation with rounding up"""
    # 50cm x 100cm = 5000 sq cm / 900 = 5.55... -> ceil = 6 units
    assert calculate_area_unit(Decimal("50"), Decimal("100")) == Decimal("6")
    
    # 30cm x 30cm = 900 sq cm / 900 = 1 unit
    assert calculate_area_unit(Decimal("30"), Decimal("30")) == Decimal("1")
    
    # Small piece: 10cm x 10cm = 100 sq cm / 900 = 0.11... -> ceil = 1 unit
    assert calculate_area_unit(Decimal("10"), Decimal("10")) == Decimal("1")

def test_create_product_rfq_item():
    """Test creating a standard product RFQ item"""
    mock_db = Mock(spec=Session)
    
    catalog_item = CatalogItem(
        id="cat-1",
        item_no="P-001",
        name="Test Product",
        type="product",
        unit="pcs",
        reference_cost=Decimal("100"),
        default_price=Decimal("200"),
        description="Original Desc",
        tax_category="tax-1"
    )
    
    rfq_item = create_rfq_item_from_catalog(
        db=mock_db,
        rfq_id="rfq-1",
        catalog_item=catalog_item,
        quantity=Decimal("5")
    )
    
    # Verify snapshot fields
    assert rfq_item.catalog_item_id == "cat-1"
    assert rfq_item.source_item_no == "P-001"
    assert rfq_item.type == "product"
    
    # Verify editable fields
    assert rfq_item.name == "Test Product"
    assert rfq_item.quantity == Decimal("5")
    assert rfq_item.unit == "pcs"
    assert rfq_item.selling_price == Decimal("200")
    
    # Verify DB interactions
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

def test_create_output_rfq_item_valid():
    """Test creating an output RFQ item with dimensions"""
    mock_db = Mock(spec=Session)
    
    catalog_item = CatalogItem(
        id="cat-2",
        item_no="O-001",
        name="Test Output",
        type="output",
        unit="材",
        reference_cost=Decimal("50"),
        default_price=Decimal("100")
    )
    
    rfq_item = create_rfq_item_from_catalog(
        db=mock_db,
        rfq_id="rfq-1",
        catalog_item=catalog_item,
        quantity=Decimal("1"),
        length_cm=Decimal("90"),
        width_cm=Decimal("100")
    )
    
    # Verify dimensions and calculation
    assert rfq_item.length_cm == Decimal("90")
    assert rfq_item.width_cm == Decimal("100")
    assert rfq_item.area_unit == Decimal("10")
    assert rfq_item.type == "output"

def test_create_output_rfq_item_missing_dims():
    """Test that creating output item without dimensions fails"""
    mock_db = Mock(spec=Session)
    
    catalog_item = CatalogItem(
        id="cat-2",
        type="output"
    )
    
    with pytest.raises(ValueError, match="Output type requires length_cm and width_cm"):
        create_rfq_item_from_catalog(
            db=mock_db,
            rfq_id="rfq-1",
            catalog_item=catalog_item,
            quantity=Decimal("1")
        )

def test_update_rfq_item_recalculation():
    """Test updating dimensions triggers recalculation"""
    mock_db = Mock(spec=Session)
    
    # Existing item: 90x100 = 10 units
    rfq_item = RFQItem(
        id="item-1",
        type="output",
        length_cm=Decimal("90"),
        width_cm=Decimal("100"),
        area_unit=Decimal("10")
    )
    
    # Update to 50x100 = 6 units
    update_data = {
        "length_cm": Decimal("50"),
        # width_cm unchanged (100)
    }
    
    updated = update_rfq_item_with_recalculation(
        db=mock_db,
        db_obj=rfq_item,
        update_data=update_data
    )
    
    assert updated.length_cm == Decimal("50")
    assert updated.width_cm == Decimal("100")
    assert updated.area_unit == Decimal("6")  # Recalculated!
    
    mock_db.commit.assert_called_once()

def test_update_immutable_fields_ignored():
    """Test that immutable fields in update_data are ignored"""
    mock_db = Mock(spec=Session)
    
    rfq_item = RFQItem(
        id="item-1",
        type="product",
        catalog_item_id="original-cat-id",
        source_item_no="P-001"
    )
    
    update_data = {
        "name": "New Name",
        "catalog_item_id": "hacked-id",
        "source_item_no": "hacked-no",
        "type": "hacked-type"
    }
    
    updated = update_rfq_item_with_recalculation(
        db=mock_db,
        db_obj=rfq_item,
        update_data=update_data
    )
    
    assert updated.name == "New Name"
    assert updated.catalog_item_id == "original-cat-id"  # Unchanged
    assert updated.source_item_no == "P-001"  # Unchanged
