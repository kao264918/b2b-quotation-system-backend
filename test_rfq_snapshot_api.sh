#!/bin/bash
# RFQ Catalog Snapshot API Test Suite

BASE_URL="http://localhost:8000/api/v1"
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_test() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

log_pass() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_fail() {
    echo -e "${RED}✗ $1${NC}"
}

echo -e "${BLUE}============================================================"
echo "RFQ Catalog Snapshot API Test Suite"
echo "============================================================${NC}"
echo "Base URL: $BASE_URL"
echo "Time: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Prerequisites: Need existing Catalog items and RFQ
# Let's create them first

# Test 1: Create Catalog Product Item
log_test "Test 1: Create Catalog Product for testing"
PRODUCT_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/catalog/items" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Product for RFQ",
        "type": "product",
        "unit": "pcs",
        "reference_cost": 100.00,
        "default_price": 200.00
    }')
HTTP_CODE=$(echo "$PRODUCT_RESP" | tail -n1)
PRODUCT_BODY=$(echo "$PRODUCT_RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    PRODUCT_ID=$(echo "$PRODUCT_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    PRODUCT_ITEM_NO=$(echo "$PRODUCT_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['item_no'])")
    log_pass "Created product: $PRODUCT_ITEM_NO (ID: $PRODUCT_ID)"
else
    log_fail "Failed to create product: HTTP $HTTP_CODE"
    exit 1
fi

# Test 2: Create Catalog Output Item
log_test "Test 2: Create Catalog Output for testing"
OUTPUT_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/catalog/items" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Steel Sheet for RFQ",
        "type": "output",
        "unit": "材",
        "reference_cost": 50.00,
        "default_price": 100.00
    }')
HTTP_CODE=$(echo "$OUTPUT_RESP" | tail -n1)
OUTPUT_BODY=$(echo "$OUTPUT_RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    OUTPUT_ID=$(echo "$OUTPUT_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    OUTPUT_ITEM_NO=$(echo "$OUTPUT_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['item_no'])")
    log_pass "Created output: $OUTPUT_ITEM_NO (ID: $OUTPUT_ID)"
else
    log_fail "Failed to create output: HTTP $HTTP_CODE"
    exit 1
fi

# Test 3: Create Customer (required for RFQ)
log_test "Test 3: Create Customer for RFQ"
CUSTOMER_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/customers" \
    -H "Content-Type: application/json" \
    -d '{
        "company_name": "Test Customer for RFQ",
        "company_email": "test@example.com",
        "status": "active"
    }')
HTTP_CODE=$(echo "$CUSTOMER_RESP" | tail -n1)
CUSTOMER_BODY=$(echo "$CUSTOMER_RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    CUSTOMER_ID=$(echo "$CUSTOMER_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    log_pass "Created customer: $CUSTOMER_ID"
else
    log_fail "Failed to create customer: HTTP $HTTP_CODE"
    exit 1
fi

# Test 4: Create RFQ
log_test "Test 4: Create RFQ"
RFQ_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/rfqs" \
    -H "Content-Type: application/json" \
    -d "{
        \"customer_id\": \"$CUSTOMER_ID\",
        \"title\": \"Test RFQ for Catalog Snapshot\",
        \"status\": \"draft\"
    }")
HTTP_CODE=$(echo "$RFQ_RESP" | tail -n1)
RFQ_BODY=$(echo "$RFQ_RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    RFQ_ID=$(echo "$RFQ_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    log_pass "Created RFQ: $RFQ_ID"
else
    log_fail "Failed to create RFQ: HTTP $HTTP_CODE"
    echo "Response: $RFQ_BODY"
    exit 1
fi

# Test 5: Add Product to RFQ (Snapshot)
log_test "Test 5: Add Product Item to RFQ from Catalog"
ITEM_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/rfqs/$RFQ_ID/items/from-catalog" \
    -H "Content-Type: application/json" \
    -d "{
        \"catalog_item_id\": \"$PRODUCT_ID\",
        \"quantity\": 5
    }")
HTTP_CODE=$(echo "$ITEM_RESP" | tail -n1)
ITEM_BODY=$(echo "$ITEM_RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    PRODUCT_RFQ_ITEM_ID=$(echo "$ITEM_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    SOURCE_ITEM_NO=$(echo "$ITEM_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('source_item_no', 'N/A'))")
    TYPE=$(echo "$ITEM_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['type'])")
    log_pass "Added product item: source_item_no=$SOURCE_ITEM_NO, type=$TYPE"
else
    log_fail "Failed to add product: HTTP $HTTP_CODE"
    echo "Response: $ITEM_BODY"
fi

# Test 6: Add Output to RFQ WITHOUT dimensions (should fail)
log_test "Test 6: Add Output without dimensions (expect 400)"
ITEM_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/rfqs/$RFQ_ID/items/from-catalog" \
    -H "Content-Type: application/json" \
    -d "{
        \"catalog_item_id\": \"$OUTPUT_ID\",
        \"quantity\": 1
    }")
HTTP_CODE=$(echo "$ITEM_RESP" | tail -n1)

if [ "$HTTP_CODE" = "400" ]; then
    log_pass "400 returned (Output requires dimensions)"
else
    log_fail "Expected 400, got $HTTP_CODE"
fi

# Test 7: Add Output to RFQ WITH dimensions
log_test "Test 7: Add Output with dimensions (90×100 cm = 10 材)"
ITEM_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/rfqs/$RFQ_ID/items/from-catalog" \
    -H "Content-Type: application/json" \
    -d "{
        \"catalog_item_id\": \"$OUTPUT_ID\",
        \"quantity\": 3,
        \"length_cm\": 90,
        \"width_cm\": 100
    }")
HTTP_CODE=$(echo "$ITEM_RESP" | tail -n1)
ITEM_BODY=$(echo "$ITEM_RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    OUTPUT_RFQ_ITEM_ID=$(echo "$ITEM_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    AREA_UNIT=$(echo "$ITEM_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('area_unit', 'N/A'))")
    
    if [ "$AREA_UNIT" = "10" ] || [ "$AREA_UNIT" = "10.0" ] || [ "$AREA_UNIT" = "10.00" ]; then
        log_pass "Added output: area_unit=$AREA_UNIT (90×100/900=10) ✓"
    else
        log_fail "Expected area_unit=10, got $AREA_UNIT"
    fi
else
    log_fail "Failed to add output: HTTP $HTTP_CODE"
    echo "Response: $ITEM_BODY"
fi

# Test 8: Update Output dimensions (50×100 cm  = ceil(5.55) = 6 材)
log_test "Test 8: Update Output dimensions (50×100 cm = 6 材)"
UPDATE_RESP=$(curl -s -w "\n%{http_code}" -X PUT "$BASE_URL/rfqs/$RFQ_ID/items/$OUTPUT_RFQ_ITEM_ID" \
    -H "Content-Type: application/json" \
    -d '{
        "length_cm": 50,
        "width_cm": 100
    }')
HTTP_CODE=$(echo "$UPDATE_RESP" | tail -n1)
UPDATE_BODY=$(echo "$UPDATE_RESP" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    AREA_UNIT=$(echo "$UPDATE_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('area_unit', 'N/A'))")
    
    if [ "$AREA_UNIT" = "6" ] || [ "$AREA_UNIT" = "6.0" ] || [ "$AREA_UNIT" = "6.00" ]; then
        log_pass "Updated area_unit=$AREA_UNIT (50×100/900=5.55→6) ✓"
    else
        log_fail "Expected area_unit=6, got $AREA_UNIT"
    fi
else
    log_fail "Failed to update: HTTP $HTTP_CODE"
    echo "Response: $UPDATE_BODY"
fi

# Cleanup
echo -e "\n${YELLOW}Cleaning up test data...${NC}"
curl -s -X DELETE "$BASE_URL/rfqs/$RFQ_ID" > /dev/null
curl -s -X DELETE "$BASE_URL/catalog/items/$PRODUCT_ID" > /dev/null
curl -s -X DELETE "$BASE_URL/catalog/items/$OUTPUT_ID" > /dev/null
curl -s -X DELETE "$BASE_URL/customers/$CUSTOMER_ID" > /dev/null

echo -e "\n${GREEN}============================================================"
echo "All tests completed!"
echo "============================================================${NC}"
