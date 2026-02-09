#!/bin/bash

BASE_URL="http://localhost:8000/api/v1/auth"
COOKIE_FILE="cookies.txt"

# 1. Login
echo "Attempting Login..."
curl -c $COOKIE_FILE -b $COOKIE_FILE -X POST "$BASE_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Password123", "remember_me": true}' \
  -s > login_response.json

if grep -q "200" <(echo $(curl -s -o /dev/null -w "%{http_code}" -c $COOKIE_FILE -b $COOKIE_FILE -X POST "$BASE_URL/login" -H "Content-Type: application/json" -d '{"email": "admin@example.com", "password": "Password123"}')); then
    echo "Login successful (HTTP 200 checks out broadly, checking json...)"
else
    echo "Login failed or warning."
fi

# Check Login content
cat login_response.json
echo ""

# 2. Me
echo "Fetching /me..."
curl -c $COOKIE_FILE -b $COOKIE_FILE "$BASE_URL/me" -s > me_response.json
cat me_response.json
echo ""

# Verify Email in Me
if grep -q "admin@example.com" me_response.json; then
    echo "User verification SUCCESS"
else
    echo "User verification FAILED"
fi

# 3. Logout
echo "Logging out..."
curl -c $COOKIE_FILE -b $COOKIE_FILE -X POST "$BASE_URL/logout" -s
echo ""

# 4. Verify Logout
echo "Verifying logout (expecting 401)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -c $COOKIE_FILE -b $COOKIE_FILE "$BASE_URL/me")
echo "HTTP Code: $HTTP_CODE"

if [ "$HTTP_CODE" -eq "401" ]; then
    echo "Logout verification SUCCESS"
else
    echo "Logout verification FAILED (Expected 401)"
fi

rm $COOKIE_FILE login_response.json me_response.json
