import joblib
import pandas as pd
import datetime
import os
import requests

# 请把这里替换为你申请的百度地图 AK
BAIDU_AK = "rOTvJe6VTInuQkUenZfTm1EGzm9PYoCq"  

def get_real_weather():
    """
    调用百度地图API获取上海市实时天气，并转换为模型需要的数字编码
    """
    # 310100 是上海市的行政区划代码
    url = f"https://api.map.baidu.com/weather/v1/?district_id=310100&data_type=now&ak={BAIDU_AK}"
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get("status") == 0: # 请求成功
            weather_text = data["result"]["now"]["text"]
            print(f"当前上海真实天气: {weather_text}")
            
            # 【注意】：这里需要映射为你模型训练时的编码规则
            # 假设你当时训练模型时：0代表晴天/多云/阴，1代表下雨/下雪
            if "雨" in weather_text or "雪" in weather_text or "暴" in weather_text:
                return 1
            else:
                return 0
    except Exception as e:
        print(f"⚠️ 天气接口请求失败，使用默认天气兜底。原因: {e}")
        
    return 0  # 如果网络断开或请求失败，兜底返回 0

def predict_day():
    """
    预测未来24小时的车流量
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, 'model.pkl')
    
    model = joblib.load(model_path)
    
    now = datetime.datetime.now()
    day_of_week = now.weekday()          
    is_weekend = 1 if day_of_week >= 5 else 0
    
    # 🌟 动态获取真实的实时天气！
    real_weather_code = get_real_weather()
    
    df = pd.DataFrame({
        'hour': range(24),
        'day_of_week': [day_of_week] * 24,
        'is_weekend': [is_weekend] * 24,
        'weather': [real_weather_code] * 24
    })
    
    preds = model.predict(df)
    
    predictions = []
    for h, p in zip(range(24), preds):
        predictions.append({
            "hour": h,
            "predicted_cars": int(max(0, p))
        })
        
    return predictions

if __name__ == "__main__":
    print(predict_day())