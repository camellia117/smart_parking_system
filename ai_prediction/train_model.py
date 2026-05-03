import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from backend.database import SessionLocal
from backend.models import ParkingRecord
import joblib
import random
from datetime import datetime, timedelta

def generate_synthetic_data(days=365):
    """
    数据增强引擎：模拟一整年的城市潮汐停车规律作为训练基线
    解决数据库初期数据太少导致大屏预测成直线的死板问题。
    """
    synthetic_data = []
    start_date = datetime(2023, 1, 1)
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        dow = current_date.weekday()
        is_weekend = 1 if dow >= 5 else 0
        # 模拟 25% 概率出现雨雪坏天气
        weather = np.random.choice([0, 1], p=[0.75, 0.25]) 
        
        for hour in range(24):
            # 潮汐算法：工作日早晚高峰，周末商圈平滑高峰
            if is_weekend:
                # 周末：10点到21点处于商圈热度较高状态
                if 10 <= hour <= 21:
                    base_cars = np.random.normal(85, 15)
                else:
                    base_cars = np.random.normal(20, 5)
            else:
                # 工作日：通勤双黄线 (8-10点，17-19点)
                if 8 <= hour <= 10 or 17 <= hour <= 19:
                    base_cars = np.random.normal(160, 25)
                elif 10 < hour < 17:
                    base_cars = np.random.normal(110, 20)
                else:
                    base_cars = np.random.normal(15, 6)
            
            # 天气影响因子：坏天气导致工作日开车通勤增加(+15%)，周末出门游玩减少(-20%)
            if weather == 1:
                if is_weekend:
                    base_cars *= 0.8
                else:
                    base_cars *= 1.15
                    
            synthetic_data.append({
                "hour": hour,
                "day_of_week": dow,
                "is_weekend": is_weekend,
                "weather": weather,
                "count": max(0, int(base_cars))
            })
            
    return pd.DataFrame(synthetic_data)

print("⏳ 正在注入潮汐先验数据并读取真实数据库...")

# 1. 获取增强型基线数据
base_df = generate_synthetic_data()

# 2. 获取真实数据库数据（你的原逻辑）
db = SessionLocal()
records = db.query(ParkingRecord).all()

db_data = []
for r in records:
    # 使用你的密码本逻辑分配天气
    historical_weather = random.choice([0, 0, 0, 1]) 
    db_data.append({
        "hour": r.enter_time.hour,
        "day_of_week": r.enter_time.weekday(),
        "is_weekend": 1 if r.enter_time.weekday() >= 5 else 0,
        "weather": historical_weather
    })

# 3. 数据融合与训练
if len(db_data) > 0:
    real_df = pd.DataFrame(db_data)
    real_hourly = real_df.groupby(["hour", "day_of_week", "is_weekend", "weather"]).size().reset_index(name="count")
    # 将真实数据与模拟先验数据合并 (真实数据可以增加权重)
    final_df = pd.concat([base_df, real_hourly * 3]) # 真实数据赋予3倍权重
else:
    final_df = base_df

# 分离特征和标签
X = final_df[["hour", "day_of_week", "is_weekend", "weather"]]
y = final_df["count"]

# 4. 训练模型 (加入更深的树以拟合潮汐曲线)
model = RandomForestRegressor(n_estimators=150, max_depth=10, random_state=42)
model.fit(X, y)

# 保存模型
joblib.dump(model, "ai_prediction/model.pkl")
print(f"✅ 模型重构完成！融合了 {len(db_data)} 条真实记录。模型已保存至 ai_prediction/model.pkl")