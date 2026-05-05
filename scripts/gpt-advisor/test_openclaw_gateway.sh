#!/bin/bash
# test_openclaw_gateway.sh — Test OpenCLAW gateway connectivity and auth
# Reads OPENCLAW_BASE_URL, OPENCLAW_GATEWAY_TOKEN / OPENCLAW_TOKEN, OPENCLAW_MODEL from environment

set -e

BASE_URL="${OPENCLAW_BASE_URL:-}"
TOKEN="${OPENCLAW_GATEWAY_TOKEN:-${OPENCLAW_TOKEN:-}}"
MODEL="${OPENCLAW_MODEL:-tianlu}"

if [ -z "$BASE_URL" ]; then
  echo "ERROR: OPENCLAW_BASE_URL is not set"
  echo "Please set: export OPENCLAW_BASE_URL=https://even2026.tianlu2026.org"
  exit 1
fi

if [ -z "$TOKEN" ]; then
  echo "ERROR: neither OPENCLAW_GATEWAY_TOKEN nor OPENCLAW_TOKEN is set"
  echo "Please export OPENCLAW_GATEWAY_TOKEN before running this script."
  exit 1
fi

echo "=== OpenCLAW Gateway Test ==="
echo "BASE_URL: $BASE_URL"
echo "MODEL: $MODEL"
echo "TOKEN: <hidden>"
echo ""

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "'"$MODEL"'",
    "messages": [
      {"role": "user", "content": "请用一句话确认你能读取天禄记忆。"}
    ]
  }')

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS:/d')

echo "HTTP Status: $HTTP_STATUS"
echo ""
echo "Response:"
echo "$BODY" | head -50

if [ "$HTTP_STATUS" = "401" ]; then
  echo ""
  echo "ERROR: 401 Unauthorized — check OPENCLAW_GATEWAY_TOKEN / OPENCLAW_TOKEN"
  exit 1
elif [ "$HTTP_STATUS" = "200" ]; then
  if echo "$BODY" | grep -Eqi "Gateway.*timeout|Gateway.*无法连接|Gateway.*無法連線|operation was aborted"; then
    echo ""
    echo "ERROR: OpenCLAW auth passed, but gateway agent relay timed out"
    exit 2
  else
    echo ""
    echo "SUCCESS: OpenCLAW gateway is reachable, authenticated, and returned an agent answer"
  fi
else
  echo ""
  echo "ERROR: unexpected HTTP status $HTTP_STATUS"
  exit 1
fi
