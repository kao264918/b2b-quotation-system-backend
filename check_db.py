from app.database import engine
from sqlalchemy import inspect
import textwrap

def check_schema():
    inspector = inspect(engine)
    columns = inspector.get_columns('rfqs')
    deleted_at = next((c for c in columns if c['name'] == 'deleted_at'), None)
    
    print("-" * 30)
    print("RFQS Table Columns:")
    for c in columns:
        print(f"- {c['name']} ({c['type']})")
    print("-" * 30)
    
    if deleted_at:
        print("✅ deleted_at column FOUND.")
    else:
        print("❌ deleted_at column NOT FOUND.")

if __name__ == "__main__":
    check_schema()
