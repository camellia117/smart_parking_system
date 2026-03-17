# 文件：backend/analytics.py
import pandas as pd
from backend.database import SessionLocal
from backend.models import ParkingRecord
from datetime import datetime

def statistics():
    db = SessionLocal()
    records = db.query(ParkingRecord).all()
    
    data = []
    now = datetime.now() # 获取当前时间
    
    for r in records:
        # 【修复重点】：如果车辆还没出场(leave_time为None)，用当前时间计算已停车时长
        leave = r.leave_time if r.leave_time else now
        fee = r.fee if r.fee else 0.0 # 还没出场的费用暂记为0或按目前时长计算
        
        duration = (leave - r.enter_time).total_seconds() / 3600
        
        data.append({
            "fee": fee,
            "duration": duration
        })

    df = pd.DataFrame(data)

    # 【修复重点】：即使数据为空，也返回标准的格式，不要返回空字典 {}
    if df.empty:
        return {
            "total_revenue": 0.0,
            "avg_parking_time": 0.0,
            "records": 0
        }

    return {
        "total_revenue": float(df["fee"].sum()),
        "avg_parking_time": float(df["duration"].mean()),
        "records": len(df)
    }