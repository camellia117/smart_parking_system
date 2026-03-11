import pandas as pd
from backend.database import SessionLocal
from backend.models import ParkingRecord

def statistics():

    db = SessionLocal()

    records = db.query(ParkingRecord).all()

    data = []

    for r in records:

        duration = (r.leave_time - r.enter_time).total_seconds()/3600

        data.append({
            "fee": r.fee,
            "duration": duration
        })

    df = pd.DataFrame(data)

    if df.empty:
        return {}

    return {

        "total_revenue": float(df["fee"].sum()),

        "avg_parking_time": float(df["duration"].mean()),

        "records": len(df)
    }