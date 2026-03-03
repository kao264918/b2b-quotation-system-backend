# B2B Quotation System - Backend API

FastAPI backend for B2B Quotation Management System.

## Tech Stack
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- Alembic (migrations)
- Pydantic 2.x

## Quick Start

### Local Development
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload
```

### Backend CI Gate（一鍵驗證）
```bash
cd b2b-quotation-system-backend
export DATABASE_URL="postgresql://<user>:<pass>@<host>:<port>/<db>"
./scripts/ci_gate_backend.sh
```

腳本會依序執行：
1. `alembic upgrade head`
2. `pytest -q`
3. 啟動 `uvicorn`，執行 `scripts/verify_system_integrity.py`

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Environment Variables

Copy `.env.example` to `.env` and configure:

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
CORS_ORIGINS=["http://localhost:5173"]
```

## API Endpoints

### Customer Module
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/customers | List all customers |
| POST | /api/v1/customers | Create customer |
| GET | /api/v1/customers/{id} | Get customer by ID |
| PUT | /api/v1/customers/{id} | Update customer |
| DELETE | /api/v1/customers/{id} | Delete customer |

## Deployment

This project is configured for Railway deployment.
See `railway.toml` for configuration.

## Architecture & Contracts

This backend implementation follows the system architecture
and domain contracts defined in the frontend repository:

👉 https://github.com/your-org/B2B-Quotation-System

Do NOT modify domain contracts in this repository.
If backend requirements conflict with frontend contracts,
raise a decision question instead.
