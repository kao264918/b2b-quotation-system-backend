"""
RFQ Number Generator

Generates unique RFQ numbers in format: RFQ-YYMM-SEQ
Example: RFQ-2601-001, RFQ-2601-002, RFQ-2602-001

Features:
- Sequence resets monthly
- Concurrent-safe using database locking
- Auto-expands beyond 3 digits if needed
"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional


def get_current_period() -> str:
    """Get current YYMM period string."""
    now = datetime.now()
    return now.strftime("%y%m")


def generate_rfq_number(db: Session) -> str:
    """
    Generate a unique RFQ number for the current month.
    
    Format: RFQ-YYMM-SEQ
    
    Uses database-level locking to ensure concurrent safety.
    
    Args:
        db: Database session
    
    Returns:
        str: Unique RFQ number (e.g., "RFQ-2601-001")
    """
    period = get_current_period()
    prefix = f"RFQ-{period}-"
    
    # Query for the highest sequence number in current period
    # Using FOR UPDATE to lock rows and prevent race conditions
    result = db.execute(
        text("""
            SELECT rfq_no 
            FROM rfqs 
            WHERE rfq_no LIKE :prefix 
            ORDER BY rfq_no DESC 
            LIMIT 1
            FOR UPDATE
        """),
        {"prefix": f"{prefix}%"}
    ).fetchone()
    
    if result:
        # Extract sequence number from existing RFQ number
        existing_no = result[0]
        # Get the sequence part (after the last dash)
        seq_str = existing_no.split("-")[-1]
        next_seq = int(seq_str) + 1
    else:
        next_seq = 1
    
    # Format sequence with minimum 3 digits, auto-expand if needed
    seq_width = max(3, len(str(next_seq)))
    seq_str = str(next_seq).zfill(seq_width)
    
    return f"{prefix}{seq_str}"


def parse_rfq_number(rfq_no: str) -> Optional[dict]:
    """
    Parse an RFQ number into its components.
    
    Args:
        rfq_no: RFQ number string (e.g., "RFQ-2601-001")
    
    Returns:
        dict with 'year', 'month', 'sequence' or None if invalid
    """
    if not rfq_no or not rfq_no.startswith("RFQ-"):
        return None
    
    parts = rfq_no.split("-")
    if len(parts) != 3:
        return None
    
    try:
        period = parts[1]
        year = int("20" + period[:2])
        month = int(period[2:])
        sequence = int(parts[2])
        
        return {
            "year": year,
            "month": month,
            "sequence": sequence,
        }
    except (ValueError, IndexError):
        return None
