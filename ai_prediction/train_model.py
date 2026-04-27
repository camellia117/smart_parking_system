import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from backend.database import SessionLocal
from backend.models import ParkingRecord
import joblib
import random

# ==========================================
# 1. 定义“密码本” (Label Encoding 映射字典)
# ==========================================
WEATHER_MAPPING = {
    "晴": 0, 
    "多云": 0, 
    "阴": 0,
    "小雨": 1, 
    "中雨": 1, 
    "大雨": 1, 
    "暴雨": 1, 
    "雪": 1
}

db = SessionLocal()
records = db.query(ParkingRecord).all()

data = []
for r in records:
    # ==========================================
    # 2. 模拟历史天气文本 
    # (因为你的数据库当时没存天气，我们随机给个文本作为演示)
    # ==========================================
    # 假设这天可能发生的天气
    historical_weather_text = random.choice(["晴", "多云", "阴", "小雨", "大雨"])
    
    # ==========================================
    # 3. 执行特征编码 (文字 -> 数字)
    # ==========================================
    # 去密码本里查，如果查不到默认给 0 (晴天)
    weather_code = WEATHER_MAPPING.get(historical_weather_text, 0)
    
    # 将多维度特征存入列表
    data.append({
        "hour": r.enter_time.hour,
        "day_of_week": r.enter_time.weekday(),
        "is_weekend": 1 if r.enter_time.weekday() >= 5 else 0,
        "weather": weather_code  # 这里传入的就是 0 或 1 了！
    })

df = pd.DataFrame(data)

# 统计每小时、每种特征组合下的进车数
hourly = df.groupby(["hour", "day_of_week", "is_weekend", "weather"]).size().reset_index(name="count")

X = hourly[["hour", "day_of_week", "is_weekend", "weather"]]
y = hourly["count"]

# 增加树的数量提升预测精度
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X, y)

# 保存包含了天气特征的全新模型
joblib.dump(model, "ai_prediction/model.pkl")
print("✅ 模型训练完成！已成功加入天气特征编码，模型已保存至 ai_prediction/model.pkl")