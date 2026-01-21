from app.database import engine
from sqlalchemy import inspect

def check_customers():
    inspector = inspect(engine)
    columns = inspector.get_columns('customers')
    print("-" * 30)
    print("CUSTOMERS Table Columns:")
    for c in columns:
        print(f"- {c['name']} ({c['type']})")
    print("-" * 30)

if __name__ == "__main__":
    check_customers()
