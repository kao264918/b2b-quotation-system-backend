# 如何建立後端使用者 (How to Create Backend Users)

本系統目前採用 **Invite-Only (邀請制)**，若要在初始化階段或緊急情況下建立管理員帳號，可以使用後端提供的 Python 腳本。

## 📍 腳本位置
`backend/scripts/create_manual_user.py`

## 🛠️ 使用方式

### 1. 直接輸入帳號密碼
腳本會在執行時要求輸入 Email 與 Password，不需要先修改原始碼。

### 2. 在本地開發環境執行 (Local)

確保你已經啟動了本地資料庫 (Docker)，且 `.env` 設定正確。

```bash
# 切換到 backend 目錄
cd b2b-quotation-system-backend

# 啟動虛擬環境 (若有)
source venv/bin/activate

# 執行腳本
python scripts/create_manual_user.py
```

### 3. 在生產環境執行 (Production / Railway)

若要在 Railway 上建立使用者，你需要連線到生產環境資料庫。

#### 方法 A：使用 Railway CLI (推薦)
如果你有安裝 Railway CLI：
```bash
railway run python scripts/create_manual_user.py
```

#### 方法 B：手動設定 DATABASE_URL
1. 到 Railway Dashboard -> Database -> Connect -> 複製 **Postgres Connection URL**。
2. 在終端機執行：

```bash
# 設定環境變數 (Linux/Mac)
export DATABASE_URL="postgresql://postgres:PASSWORD@railway-host:port/railway"

# 執行腳本
python scripts/create_manual_user.py
```

> ⚠️ **注意**：生產環境資料庫連線字串包含敏感資訊，請勿將其 commit 到版控。

## 🔄 更新密碼
此腳本具有 **Idempotent (冪等)** 特性：
- 若 Email **不存在**：建立新使用者。
- 若 Email **已存在**：更新該使用者的密碼。

## ❓ 常見問題
**Q: 執行時出現 `ModuleNotFoundError`?**
A: 請確保你已經安裝了專案依賴 (`pip install -r requirements.txt`) 並且在正確的虛擬環境中。

**Q: 出現連線錯誤?**
A: 請檢查 `DATABASE_URL` 是否正確，以及你的 IP 是否被允許連線到資料庫 (若有防火牆設定)。
