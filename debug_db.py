from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def check_db():
    try:
        with engine.connect() as conn:
            # Check columns in rfqs table
            result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'rfqs'"))
            columns = {row[0]: row[1] for row in result}
            print(f"Columns in rfqs table: {list(columns.keys())}")
            
            if 'accounting_status' not in columns:
                print("ERROR: accounting_status column missing!")
            else:
                print("accounting_status column exists.")
                
                # Check for NULL values
                result = conn.execute(text("SELECT id, accounting_status FROM rfqs WHERE accounting_status IS NULL"))
                null_rows = result.fetchall()
                if null_rows:
                    print(f"ERROR: Found {len(null_rows)} rows with NULL accounting_status:")
                    for row in null_rows:
                        print(row)
                    
                    # Fix NULLs
                    print("Attempting to fix NULL values...")
                    conn.execute(text("UPDATE rfqs SET accounting_status = 'unfulfilled' WHERE accounting_status IS NULL"))
                    conn.commit()
                    print("Fixed NULL values.")
                else:
                    print("No NULL values found for accounting_status.")
                    
                # Check status values
                result = conn.execute(text("SELECT DISTINCT status FROM rfqs"))
                statuses = [row[0] for row in result]
                print(f"Distinct statuses in DB: {statuses}")
                
                invalid_statuses = [s for s in statuses if s in ('won', 'lost')]
                if invalid_statuses:
                    print(f"ERROR: Found invalid statuses: {invalid_statuses}")
                    print("Attempting to migrate 'won' -> 'closed' and 'lost' -> 'discarded'...")
                    conn.execute(text("UPDATE rfqs SET status = 'closed' WHERE status = 'won'"))
                    conn.execute(text("UPDATE rfqs SET status = 'discarded' WHERE status = 'lost'"))
                    conn.commit()
                    print("Migrated invalid statuses.")
                    
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    check_db()
