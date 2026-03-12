# 文件：backend/crud.py
from backend.database import SessionLocal
from backend.models import ParkingRecord, ParkingLot

def get_all_records():
    db = SessionLocal()
    return db.query(ParkingRecord).all()

# 获取所有停车场实时状态
def get_all_lots():
    db = SessionLocal()
    return db.query(ParkingLot).all()