from backend.database import SessionLocal
from backend.models import ParkingRecord

def get_all_records():

    db = SessionLocal()

    return db.query(ParkingRecord).all()