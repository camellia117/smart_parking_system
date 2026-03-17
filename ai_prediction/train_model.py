import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from backend.database import SessionLocal
from backend.models import ParkingRecord
import joblib

db = SessionLocal()
records = db.query(ParkingRecord).all()

data = []
for r in records:
    # 提取多维度特征
    data.append({
        "hour": r.enter_time.hour,
        "day_of_week": r.enter_time.weekday(),
        "is_weekend": 1 if r.enter_time.weekday() >= 5 else 0,
        "weather": getattr(r, 'weather_type', 0)
    })

df = pd.DataFrame(data)
# 统计每小时、每种特征组合下的进车数
hourly = df.groupby(["hour", "day_of_week", "is_weekend", "weather"]).size().reset_index(name="count")

X = hourly[["hour", "day_of_week", "is_weekend", "weather"]]
y = hourly["count"]

# 增加树的数量提升预测精度
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X, y)

joblib.dump(model, "ai_prediction/model.pkl")