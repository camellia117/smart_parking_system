import sys
import os
import pandas as pd
# 导入数据库配置
from backend.database import SessionLocal, engine
from backend import models

# ==========================================
# 1. 自动路径与环境设置
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 直接使用你的绝对路径
FILE_PATH = r"D:\毕业设计\十天天气预报.xlsx"

def import_weather_from_excel():
    print(f"⏳ 正在从 {FILE_PATH} 提取天气数据...")
    
    if not os.path.exists(FILE_PATH):
        print(f"❌ 错误：在 {FILE_PATH} 找不到文件，请核对路径！")
        return

    # 读取 Excel 文件
    try:
        # 使用 openpyxl 引擎读取 xlsx
        df = pd.read_excel(FILE_PATH)
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return

    db = SessionLocal()
    # 确保数据库中存在 weather_history 表结构
    models.Base.metadata.create_all(bind=engine)

    count = 0
    for _, row in df.iterrows():
        # 根据你提供的文件内容提取关键字段
        # 处理日期：从 "2024-01-18 00:00:00" 提取日期部分
        date_raw = str(row['forecastdate'])
        date_str = date_raw[:10] 
        weather_text = str(row['dayweather'])
        
        # 判定是否为降水天气（核心特征编码）
        is_rainy = 1 if any(word in weather_text for word in ["雨", "雪", "小雨", "阵雨"]) else 0
        
        # 查重逻辑：防止重复导入同一天的天气
        existing = db.query(models.WeatherHistory).filter(models.WeatherHistory.date == date_str).first()
        
        if not existing:
            new_weather = models.WeatherHistory(
                date=date_str,
                weather_text=weather_text,
                is_rainy=is_rainy
            )
            db.add(new_weather)
            count += 1

    db.commit()
    db.close()
    print(f"✅ 导入成功！共向数据库同步了 {count} 条历史天气观测记录。")

if __name__ == "__main__":
    import_weather_from_excel()