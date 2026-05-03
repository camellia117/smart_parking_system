import sys
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib
import random
from datetime import datetime, timedelta

# ==========================================
# 1. 自动修复路径：确保从项目根目录运行不报错
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from backend.database import SessionLocal #
from backend.models import ParkingRecord, WeatherHistory #

def generate_synthetic_tidal_data(days=180):
    """
    数据增强：生成具有“潮汐效应”的基线数据，解决冷启动数据不足问题
    """
    synthetic_data = []
    start_date = datetime(2024, 1, 1)
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        dow = current_date.weekday()
        is_we = 1 if dow >= 5 else 0
        # 模拟基线天气分布
        base_weather = np.random.choice([0, 1], p=[0.7, 0.3]) 
        
        for hour in range(24):
            # 根据办公/商业区混合模式设定潮汐基线
            if is_we:
                # 周末商圈模式：午后平滑高峰
                base_cars = np.random.normal(90, 15) if 11 <= hour <= 20 else np.random.normal(25, 8)
            else:
                # 工作日通勤模式：早晚双峰
                if 8 <= hour <= 10 or 17 <= hour <= 19:
                    base_cars = np.random.normal(150, 20)
                elif 10 < hour < 17:
                    base_cars = np.random.normal(80, 15)
                else:
                    base_cars = np.random.normal(20, 5)
            
            # 天气惩罚因子
            if base_weather == 1: base_cars *= 0.85 if is_we else 1.1

            synthetic_data.append({
                "hour": hour,
                "day_of_week": dow,
                "is_weekend": is_we,
                "weather": base_weather,
                "count": max(0, int(base_cars))
            })
    return pd.DataFrame(synthetic_data)

def train_professional_model():
    print("⏳ 正在启动深度学习训练引擎...")
    
    db = SessionLocal() #
    
    # ==========================================
    # 2. 真实数据对齐逻辑
    # ==========================================
    records = db.query(ParkingRecord).all() #
    real_data_list = []
    
    for r in records:
        # 提取日期键值
        date_key = r.enter_time.strftime('%Y-%m-%d')
        
        # 从数据库中匹配当天的【真实历史天气】
        weather_log = db.query(WeatherHistory).filter(WeatherHistory.date == date_key).first()
        # 如果有真实天气记录则使用，否则默认 0
        actual_weather = weather_log.is_rainy if weather_log else 0
        
        real_data_list.append({
            "hour": r.enter_time.hour,
            "day_of_week": r.enter_time.weekday(),
            "is_weekend": 1 if r.enter_time.weekday() >= 5 else 0,
            "weather": actual_weather
        })

    # ==========================================
    # 3. 数据融合与模型拟合
    # ==========================================
    # 获取基线模拟数据
    base_df = generate_synthetic_tidal_data()
    
    if len(real_data_list) > 0:
        real_df = pd.DataFrame(real_data_list)
        # 统计真实的小时流量，并赋予 5 倍权重，让模型更偏好真实发生的规律
        real_hourly = real_df.groupby(["hour", "day_of_week", "is_weekend", "weather"]).size().reset_index(name="count")
        train_df = pd.concat([base_df, real_hourly, real_hourly, real_hourly, real_hourly, real_hourly])
        print(f"📊 成功融合 {len(real_data_list)} 条真实停车记录与历史天气映射。")
    else:
        train_df = base_df
        print("⚠️ 未发现真实停车记录，将使用基线潮汐模型进行冷启动训练。")

    X = train_df[["hour", "day_of_week", "is_weekend", "weather"]]
    y = train_df["count"]

    # 使用随机森林回归，增加树深度以捕捉细微的天气波动
    model = RandomForestRegressor(n_estimators=150, max_depth=12, random_state=42)
    model.fit(X, y)

    # ==========================================
    # 4. 模型固化
    # ==========================================
    model_save_path = os.path.join(BASE_DIR, "ai_prediction", "model.pkl") #
    joblib.dump(model, model_save_path)
    print(f"✅ 优化完成！模型已存至: {model_save_path}")
    
    db.close()

if __name__ == "__main__":
    train_professional_model()