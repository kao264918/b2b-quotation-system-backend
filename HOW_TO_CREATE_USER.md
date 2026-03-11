# 如何建立帳號

由於目前系統沒有自助註冊流程，需要手動從後端建立帳號。

## 方法 1: Railway CLI（推薦 — Production）

### 安裝 Railway CLI（如果沒有的話）
```bash
npm i -g @railway/cli
```

### 登入並連結專案
```bash
cd b2b-quotation-system-backend
railway login
railway link  # 選擇你的 production 專案
```

### 建立 Production 帳號
```bash
railway run -e EMAIL="user@example.com" -e PASSWORD="Password123!" -e FULL_NAME="Example User" python scripts/create_user_any_db.py
```

---

## 方法 2: 本地連線到 Production DB

### 前提
需要有 production 的 `DATABASE_URL`（從 Railway 控制台取得）

### 執行
```bash
cd b2b-quotation-system-backend
source venv/bin/activate

# 使用 production DATABASE_URL
DATABASE_URL="postgresql://user:pass@host:port/dbname" \
EMAIL="user@example.com" \
PASSWORD="SecurePass123" \
python scripts/create_user_any_db.py
```

---

## 方法 3: 本地資料庫（開發/測試）

```bash
cd b2b-quotation-system-backend
source venv/bin/activate

# 使用 .env 中的 DATABASE_URL
EMAIL="user@example.com" PASSWORD="Password123!" python scripts/create_user_any_db.py

# 或自訂帳密
EMAIL="custom@example.com" PASSWORD="AnotherPassword123!" FULL_NAME="Example User" python scripts/create_user_any_db.py
```

---

## 環境變數說明

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DATABASE_URL` | `.env` 中的值 | PostgreSQL 連線字串（必填） |
| `EMAIL` | 無預設值 | 帳號 Email（必填） |
| `PASSWORD` | 無預設值 | 帳號密碼（明碼輸入，腳本內會自動 hash） |
| `FULL_NAME` | `Example User` | 使用者全名 |

---

## 安全提醒

⚠️ **Production DATABASE_URL 是敏感資訊，不要 commit 到 Git**

建議做法：
1. 從 Railway 控制台複製 DATABASE_URL
2. 暫時用環境變數設定
3. 用完立即清除 shell history

```bash
# 使用後清除 history
history -d $(history 1)
```
