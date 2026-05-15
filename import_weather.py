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

# 【核心修改】使用动态路径，自动在当前文件夹下寻找 Excel
FILE_PATH = os.path.join(BASE_DIR, "十天天气预报.xlsx")

def import_weather_from_excel():
    print(f"⏳ 正在从 {FILE_PATH} 提取天气数据...")
    
    if not os.path.exists(FILE_PATH):
        print(f"❌ 错误：在 {FILE_PATH} 找不到文件，请确认 Excel 文件已上传到服务器根目录！")
        return

    # 读取 Excel 文件
    try:
        df = pd.read_excel(FILE_PATH)
        df = df.fillna("") # 【新增】空值填充，防止出现 nan 导致代码崩溃
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return

    db = SessionLocal()
    # 确保数据库中存在 weather_history 表结构
    models.Base.metadata.create_all(bind=engine)

    count = 0
    skip_count = 0
    
    for _, row in df.iterrows():
        # 【新增】安全获取字段，跳过 Excel 里的空白行
        date_raw = str(row.get('forecastdate', ''))
        if not date_raw or date_raw.strip() == "" or date_raw == "nan":
            continue
            
        # 处理日期：从 "2024-01-18 00:00:00" 提取日期部分
        date_str = date_raw[:10] 
        weather_text = str(row.get('dayweather', ''))
        
        # 判定是否为降水天气（核心特征编码）
        is_rainy = 1 if any(word in weather_text for word in ["雨", "雪", "小雨", "阵雨"]) else 0
        
        # 查重逻辑：防止重复导入同一天的天气 (你原本就写得很好的逻辑)
        existing = db.query(models.WeatherHistory).filter(models.WeatherHistory.date == date_str).first()
        
        if not existing:
            new_weather = models.WeatherHistory(
                date=date_str,
                weather_text=weather_text,
                is_rainy=is_rainy
            )
            db.add(new_weather)
            count += 1
        else:
            skip_count += 1

    db.commit()
    db.close()
    print(f"✅ 导入成功！共向数据库同步了 {count} 条历史天气记录，跳过了 {skip_count} 条重复数据。")

if __name__ == "__main__":
    import_weather_from_excel()