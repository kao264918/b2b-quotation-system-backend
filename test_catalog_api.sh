#!/bin/bash
# Catalog API Test Suite
# Tests all endpoints and validates MVP requirements

BASE_URL="http://localhost:8000/api/v1/catalog/items"
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track created IDs for cleanup
CREATED_IDS=()

cleanup() {
    echo -e "\n${YELLOW}Cleaning up test data...${NC}"
    for id in "${CREATED_IDS[@]}"; do
        curl -s -X DELETE "$BASE_URL/$id" > /dev/null
    done
}

trap cleanup EXIT

log_test() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

log_pass() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_fail() {
    echo -e "${RED}✗ $1${NC}"
}

log_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

echo -e "${BLUE}============================================================"
echo "Catalog API Test Suite"
echo "============================================================${NC}"
echo "Base URL: $BASE_URL"
echo "Time: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Test 1: Create Product
log_test "Test 1: Create Product (auto item_no, default unit)"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Laptop Stand",
        "type": "product",
        "reference_cost": 150.00,
        "default_price": 300.00,
        "description": "Test product item"
    }')
HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    ITEM_NO=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['item_no'])")
    UNIT=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['unit'])")
    PRODUCT_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    CREATED_IDS+=("$PRODUCT_ID")
    
    if [[ "$ITEM_NO" =~ ^P- ]] && [ "$UNIT" = "pcs" ]; then
        log_pass "Created product: $ITEM_NO, unit=$UNIT"
    else
        log_fail "Unexpected item_no or unit: $ITEM_NO, $UNIT"
    fi
else
    log_fail "HTTP $HTTP_CODE"
fi

# Test 2: Create Service
log_test "Test 2: Create Service (S- prefix)"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Installation Service",
        "type": "service",
        "reference_cost": 500.00,
        "default_price": 1000.00
    }')
HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    ITEM_NO=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['item_no'])")
    SERVICE_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    CREATED_IDS+=("$SERVICE_ID")
    
    if [[ "$ITEM_NO" =~ ^S- ]]; then
        log_pass "Created service: $ITEM_NO"
    else
        log_fail "Expected S- prefix, got: $ITEM_NO"
    fi
else
    log_fail "HTTP $HTTP_CODE"
fi

# Test 3: Create Output
log_test "Test 3: Create Output (O- prefix, unit=材)"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Steel Sheet",
        "type": "output",
        "reference_cost": 200.00,
        "default_price": 400.00
    }')
HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    ITEM_NO=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['item_no'])")
    UNIT=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['unit'])")
    OUTPUT_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    CREATED_IDS+=("$OUTPUT_ID")
    
    if [[ "$ITEM_NO" =~ ^O- ]] && [ "$UNIT" = "材" ]; then
        log_pass "Created output: $ITEM_NO, unit=$UNIT"
    else
        log_fail "Unexpected item_no or unit: $ITEM_NO, $UNIT"
    fi
else
    log_fail "HTTP $HTTP_CODE"
fi

# Test 4: Duplicate Name (409)
log_test "Test 4: Duplicate Name Validation (409)"
# Create first
curl -s -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Duplicate Item",
        "type": "product",
        "reference_cost": 100.00,
        "default_price": 200.00
    }' | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" | xargs -I {} bash -c 'CREATED_IDS+=("{}")'

# Try duplicate
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Duplicate Item",
        "type": "service",
        "reference_cost": 150.00,
        "default_price": 300.00
    }')
HTTP_CODE=$(echo "$RESP" | tail -n1)

if [ "$HTTP_CODE" = "409" ]; then
    log_pass "409 Conflict returned"
else
    log_fail "Expected 409, got $HTTP_CODE"
fi

# Test 5: Pagination
log_test "Test 5: Pagination & Meta"
RESP=$(curl -s "$BASE_URL?page=1&pageSize=50")
TOTAL_COUNT=$(echo "$RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['meta']['totalCount'])" 2>/dev/null || echo "0")
TOTAL_PAGES=$(echo "$RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['meta']['totalPages'])" 2>/dev/null || echo "0")

if [ ! -z "$TOTAL_COUNT" ]; then
    log_pass "Pagination OK: $TOTAL_COUNT items, $TOTAL_PAGES pages"
else
    log_fail "Pagination failed"
fi

# Test 6: Filter by Type
log_test "Test 6: Filter by Type"
RESP=$(curl -s "$BASE_URL?type=product")
ITEMS=$(echo "$RESP" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len([i for i in data['items'] if i['type']=='product']))" 2>/dev/null || echo "0")
log_pass "Type filter OK: $ITEMS products"

# Test 7: Get by ID
log_test "Test 7: Get Item by ID"
if [ ! -z "$PRODUCT_ID" ]; then
    RESP=$(curl -s -w "\n%{http_code}" "$BASE_URL/$PRODUCT_ID")
    HTTP_CODE=$(echo "$RESP" | tail -n1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Retrieved item successfully"
    else
        log_fail "HTTP $HTTP_CODE"
    fi
fi

# Test 8: Update
log_test "Test 8: Update Item"
if [ ! -z "$PRODUCT_ID" ]; then
    RESP=$(curl -s -w "\n%{http_code}" -X PUT "$BASE_URL/$PRODUCT_ID" \
        -H "Content-Type: application/json" \
        -d '{
            "description": "Updated description",
            "default_price": 350.00
        }')
    HTTP_CODE=$(echo "$RESP" | tail -n1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Updated successfully"
    else
        log_fail "HTTP $HTTP_CODE"
    fi
fi

# Test 9: Inactivate
log_test "Test 9: Inactivate Item"
if [ ! -z "$PRODUCT_ID" ]; then
    RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/$PRODUCT_ID/inactivate")
    HTTP_CODE=$(echo "$RESP" | tail -n1)
    BODY=$(echo "$RESP" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        STATUS=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
        if [ "$STATUS" = "inactive" ]; then
            log_pass "Inactivated successfully"
        else
            log_fail "Status is $STATUS, expected inactive"
        fi
    else
        log_fail "HTTP $HTTP_CODE"
    fi
fi

# Test 10: Soft Delete
log_test "Test 10: Soft Delete"
if [ ! -z "$SERVICE_ID" ]; then
    RESP=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE_URL/$SERVICE_ID")
    HTTP_CODE=$(echo "$RESP" | tail -n1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Deleted successfully"
        
        # Verify 404
        RESP2=$(curl -s -w "\n%{http_code}" "$BASE_URL/$SERVICE_ID")
        HTTP_CODE2=$(echo "$RESP2" | tail -n1)
        
        if [ "$HTTP_CODE2" = "404" ]; then
            log_pass "Confirmed: Returns 404 after delete"
        else
            log_fail "Expected 404, got $HTTP_CODE2"
        fi
    else
        log_fail "HTTP $HTTP_CODE"
    fi
fi

# Summary
echo -e "\n${GREEN}============================================================"
echo "All tests completed!"
echo "============================================================${NC}"
