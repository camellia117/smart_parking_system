import joblib
import pandas as pd
import datetime
import os
import requests

# 请把这里替换为你申请的百度地图 AK
BAIDU_AK = "LoTLDU1fWyDkcoAoNiv5VkDj9JPAqeeW"  

def get_real_weather():
    """
    调用百度地图API获取上海市实时天气，并转换为模型需要的数字编码
    """
    url = f"https://api.map.baidu.com/weather/v1/?district_id=310100&data_type=now&ak={BAIDU_AK}"
    
    # 1. 伪装身份：穿上 Google Chrome 浏览器的“马甲”，防止被百度防火墙踢掉
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 2. 绕过代理：强制直连国内网络，防止被本地的 Gemini 翻墙代理（如端口 7897）拦截报错
    proxies = {
        "http": None,
        "https": None
    }
    
    try:
        # 将 headers 和 proxies 一起传给 requests
        response = requests.get(url, headers=headers, proxies=proxies, timeout=5)
        data = response.json()
        
        if data.get("status") == 0:
            weather_text = data["result"]["now"]["text"]
            print(f"✅ 成功获取当前上海真实天气: {weather_text}")
            
            if "雨" in weather_text or "雪" in weather_text or "暴" in weather_text:
                return 1
            else:
                return 0
        else:
            print(f"⚠️ 百度接口返回了错误信息: {data.get('message')}")
            
    except Exception as e:
        print(f"⚠️ 天气接口请求失败，使用默认天气兜底。原因: {e}")
        
    return 0

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