#!/bin/bash
# 在 Railway Production 環境建立用戶的快速腳本
# 使用方式: ./create_prod_user.sh

echo "🚂 透過 Railway 在 Production DB 建立用戶..."
echo ""

# 方法 1: Railway Run（推薦）
echo "方法 1: 使用 railway run"
echo "指令: railway run python scripts/create_manual_user.py"
echo ""

# 方法 2: 一次性 Railway 指令執行
echo "方法 2: 使用 Railway 一次性指令"
railway run --service b2b-quotation-system-backend bash -c "cd /app && python scripts/create_manual_user.py"
