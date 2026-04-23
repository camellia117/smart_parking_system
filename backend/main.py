from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel  
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend import models
from backend.crud import get_all_records, get_all_lots 
from backend.analytics import statistics
from ai_prediction.predict import predict_day
from fastapi.middleware.cors import CORSMiddleware
from . import crud, models, database
from typing import List, Optional
import random
import uuid
import string
import base64
from captcha.image import ImageCaptcha
from fastapi.responses import JSONResponse
import os 
import requests
import xmltodict
import pandas as pd
import numpy as np
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(title="SMART PARKING AI-OS API")

# ====== 全局变量：临时存储验证码 ======
mock_verification_codes = {} 
mock_captchas = {}           
mock_login_sms_codes = {}  
# 全局内存缓存：上海停车场真实物理基座
LIVE_SHANGHAI_DATA = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# =========================================================
#             1. 真实接口同步引擎 (Requirement 7)
# =========================================================
def sync_shanghai_data():
    """对接上海市大数据中心 XML 接口"""
    API_URL = "https://data.sh.gov.cn/interface/O5915184132025224/58041" 
    TOKEN = "c2b1a4da8abf581f8d2210ef0dc72cb8" # 请替换为真实 Token
    
    headers = {"content-type": "application/xml", "token": TOKEN}
    payload = "<map></map>"
    
    try:
        # 参考接口说明 docx 的调用方式
        response = requests.post(API_URL, headers=headers, data=payload, timeout=20)
        if response.status_code == 200:
            xml_dict = xmltodict.parse(response.content)
            # 解析 <result><data><Result> 层级
            records = xml_dict.get('result', {}).get('data', {}).get('Result', [])
            if not isinstance(records, list): records = [records]
            
            global LIVE_SHANGHAI_DATA
            new_data = []
            for r in records:
                if r.get('jhpt_delete') == '1': continue
                
                # 简单 POI 判定逻辑
                name = r.get('parking_name', '')
                p_type = "commercial"
                if any(x in name for x in ["大厦", "办公", "写字楼"]): p_type = "office"
                elif any(x in name for x in ["小区", "公寓", "苑"]): p_type = "residential"

                new_data.append({
                    "id": r.get('parking_id'),
                    "name": name,
                    "address": r.get('address'),
                    "total": int(r.get('total_berth', 0) or 0),
                    "battery": int(r.get('battery_berth', 0) or 0),
                    "nobarry": int(r.get('nobarry_berth', 0) or 0),
                    "company": r.get('company_manage'),
                    "phone": r.get('complained_tel'),
                    "type": p_type,
                    "lng": 121.47 + (hash(r.get('parking_id', '')) % 100) / 1000.0,
                    "lat": 31.23 + (hash(name) % 100) / 1000.0
                })
            LIVE_SHANGHAI_DATA = new_data
    except Exception as e:
        print(f"Sync Failed: {e}")

# 定时任务调度
scheduler = BackgroundScheduler()
@app.on_event("startup")
def startup_event():
    sync_shanghai_data()
    scheduler.add_job(sync_shanghai_data, 'cron', hour=3) # 凌晨3点同步更新
    scheduler.start()

# =========================================================
#             2. GIS 仿真推演引擎 (Requirement 6)
# =========================================================
def get_tide_rate(p_type: str, hour: int) -> float:
    """专家规则：POI 潮汐占用率基础值"""
    if p_type == "office":
        return 0.92 if 9 <= hour <= 17 else 0.15
    elif p_type == "residential":
        return 0.30 if 8 <= hour <= 19 else 0.95
    return 0.85 if 18 <= hour <= 21 else 0.50

@app.get("/gis_map")
def get_gis_map():
    """核心：融合 AI 因子与物理底座的 GIS 接口"""
    hour = datetime.datetime.now().hour
    # 联动 AI 预测模型：获取今日压力因子
    ai_predictions = predict_day()
    ai_factor = ai_predictions[hour]['predicted_cars'] / 100.0 # 归一化因子
    
    # 如果接口未同步，回退到 CSV 基础数据
    source = LIVE_SHANGHAI_DATA
    if not source:
        df = pd.read_csv("公共停车场基础数据.xlsx - Data.csv")
        # 此处省略 CSV 转 dict 逻辑，结构同 LIVE_SHANGHAI_DATA
    
    results = []
    for p in source:
        base_rate = get_tide_rate(p['type'], hour)
        # 仿真公式：基准 * AI修正 + 高斯噪声
        noise = np.random.normal(0, 0.04)
        final_rate = max(0.05, min(0.98, base_rate * (0.8 + ai_factor * 0.4) + noise))
        
        results.append({
            **p,
            "occupancy_rate": round(final_rate * 100, 1),
            "occupied_berth": int(p['total'] * final_rate),
            "status": "red" if final_rate > 0.85 else ("yellow" if final_rate > 0.6 else "green")
        })
    return results

  

models.Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message":"Smart Parking API"}

@app.get("/records")
def records():
    return get_all_records()

@app.get("/statistics")
def stats():
    return statistics()

@app.get("/predict")
def predict():
    return predict_day()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================================================
#             车场与计费规则管理 (ParkingLot 表)
# =========================================================
class LotCreate(BaseModel):
    name: str
    location: str
    total_spaces: int
    price_per_hour: float

class LotUpdate(BaseModel):
    price_per_hour: float
    total_spaces: int

@app.get("/lots")  
def lots(db: Session = Depends(get_db)):
    return db.query(models.ParkingLot).order_by(models.ParkingLot.id.desc()).all()

@app.post("/lots")
def create_lot(lot: LotCreate, db: Session = Depends(get_db)):
    new_lot = models.ParkingLot(
        name=lot.name, location=lot.location, 
        total_spaces=lot.total_spaces, price_per_hour=lot.price_per_hour, available_spaces=lot.total_spaces
    )
    db.add(new_lot)
    db.commit()
    db.refresh(new_lot)
    return new_lot

@app.put("/lots/{lot_id}")
def update_lot(lot_id: int, lot_data: LotUpdate, db: Session = Depends(get_db)):
    lot = db.query(models.ParkingLot).filter(models.ParkingLot.id == lot_id).first()
    if not lot: raise HTTPException(status_code=404, detail="未找到该车场")
    diff = lot_data.total_spaces - lot.total_spaces
    lot.total_spaces = lot_data.total_spaces
    lot.available_spaces = max(0, lot.available_spaces + diff)
    lot.price_per_hour = lot_data.price_per_hour
    db.commit()
    return {"message": "车场配置更新成功"}

@app.delete("/lots/{lot_id}")
def delete_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.query(models.ParkingLot).filter(models.ParkingLot.id == lot_id).first()
    if not lot: raise HTTPException(status_code=404, detail="未找到该车场")
    db.delete(lot)
    db.commit()
    return {"message": "车场已成功下线"}

    
# =========================================================
#             客户与白名单车辆管理 (User 表)
# =========================================================
class CarOwnerCreate(BaseModel):
    username: str
    car_number: str
    phone: str

@app.get("/car_owners/")
def get_car_owners(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.id.desc()).all()

@app.post("/car_owners/")
def create_car_owner(owner: CarOwnerCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.car_number == owner.car_number).first():
        raise HTTPException(status_code=400, detail="该车牌号已存在，请勿重复登记")
    new_owner = models.User(username=owner.username, car_number=owner.car_number, phone=owner.phone)
    db.add(new_owner)
    db.commit()
    db.refresh(new_owner)
    return new_owner

@app.delete("/car_owners/{owner_id}")
def delete_car_owner(owner_id: int, db: Session = Depends(get_db)):
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if not owner: raise HTTPException(status_code=404, detail="未找到该车主记录")
    db.delete(owner)
    db.commit()
    return {"message": "车辆信息已成功移除"}


# =========================================================
#                    系统管理员账号管理 
# =========================================================
class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    id: int
    username: str
    password: str
    phone: str

class ForgotPasswordReq(BaseModel):
    phone: str
    new_password: str
    code: str

@app.post("/system_users/")
def create_system_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.SystemUser).filter(models.SystemUser.username == user.username).first()
    if db_user: raise HTTPException(status_code=400, detail="Username already registered")
    if user.phone:
         db_phone = db.query(models.SystemUser).filter(models.SystemUser.phone == user.phone).first()
         if db_phone: raise HTTPException(status_code=400, detail="Phone number already registered")

    new_user = models.SystemUser(username=user.username, password=user.password, role=user.role, phone=user.phone)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/system_users/")
def get_system_users(skip: int = 0, limit: int = 100, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.SystemUser)
    if search:
        query = query.filter( (models.SystemUser.username.contains(search)) | (models.SystemUser.phone.contains(search)) )
    return query.offset(skip).limit(limit).all()

@app.delete("/system_users/{user_id}")
def delete_system_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.SystemUser).filter(models.SystemUser.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.role == "root": raise HTTPException(status_code=400, detail="Cannot delete root user")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@app.put("/system_users/")
def update_system_user(user_data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(models.SystemUser).filter(models.SystemUser.id == user_data.id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.username != user_data.username and db.query(models.SystemUser).filter(models.SystemUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if user.phone != user_data.phone and db.query(models.SystemUser).filter(models.SystemUser.phone == user_data.phone).first():
        raise HTTPException(status_code=400, detail="Phone number already exists")

    user.username = user_data.username
    user.password = user_data.password
    user.phone = user_data.phone
    db.commit()
    return {"message": "User updated successfully"}

@app.post("/send_code/")
def send_verification_code(phone: str):
    code = str(random.randint(100000, 999999))
    mock_verification_codes[phone] = code
    print(f"【模拟短信】发送给 {phone} 的验证码是: {code}")
    return {"message": "Code sent", "mock_code": code} 

@app.post("/forgot_password/")
def forgot_password(req: ForgotPasswordReq, db: Session = Depends(get_db)):
    if req.phone not in mock_verification_codes or mock_verification_codes[req.phone] != req.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    user = db.query(models.SystemUser).filter(models.SystemUser.phone == req.phone).first()
    if not user: raise HTTPException(status_code=404, detail="User with this phone not found")
    user.password = req.new_password
    db.commit()
    del mock_verification_codes[req.phone]
    return {"message": "Password reset successfully"}

# =========================================================
#                    安全登录核心逻辑
# =========================================================

@app.get("/get_captcha/")
def get_captcha():
    image = ImageCaptcha(width=120, height=42)
    captcha_text = ''.join(random.choices(string.digits, k=4))
    data = image.generate(captcha_text)
    base64_img = base64.b64encode(data.getvalue()).decode('utf-8')
    captcha_id = str(uuid.uuid4())
    mock_captchas[captcha_id] = captcha_text
    return {"captcha_id": captcha_id, "image": f"data:image/png;base64,{base64_img}"}

class SendLoginSmsReq(BaseModel):
    username: str
    password: str
    captcha_id: str
    captcha_text: str

@app.post("/send_login_sms/")
def send_login_sms(req: SendLoginSmsReq, db: Session = Depends(get_db)):
    if req.captcha_id not in mock_captchas or mock_captchas[req.captcha_id] != req.captcha_text:
        raise HTTPException(status_code=400, detail="图形验证码错误或已过期")
    del mock_captchas[req.captcha_id]

    phone = None
    if req.username == "root" and req.password == "12345678":
        phone = "13800000000" 
    else:
        user = db.query(models.SystemUser).filter(models.SystemUser.username == req.username, models.SystemUser.password == req.password).first()
        if not user: raise HTTPException(status_code=401, detail="账号或密码错误")
        if not user.phone: raise HTTPException(status_code=400, detail="该账号未绑定手机号，无法接收验证码")
        phone = user.phone

    code = str(random.randint(100000, 999999))
    mock_login_sms_codes[req.username] = code
    print(f"【模拟登录短信】发送给 {req.username} (手机: {phone}) 的验证码是: {code}")
    
    masked_phone = phone[:3] + "****" + phone[-4:]
    return {"message": "短信发送成功", "phone": masked_phone, "mock_code": code}

class LoginReq(BaseModel):
    username: str
    sms_code: str  

@app.post("/login/")
def login(req: LoginReq, db: Session = Depends(get_db)):
    if req.username not in mock_login_sms_codes or mock_login_sms_codes[req.username] != req.sms_code:
        raise HTTPException(status_code=401, detail="短信验证码错误或已过期")
    del mock_login_sms_codes[req.username]

    if req.username == "root":
        return {"message": "Login successful", "role": "dev", "username": "root", "phone": "13800000000"}

    user = db.query(models.SystemUser).filter(models.SystemUser.username == req.username).first()
    return {"message": "Login successful", "role": user.role, "username": user.username, "phone": user.phone}

# =========================================================
#             🌟 终极核心：原生 REST 接入 Gemini 云端大脑
# =========================================================
import requests
from dotenv import load_dotenv
import os

load_dotenv()  
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PROXIES = {
    "http": "http://127.0.0.1:7897",
    "https": "http://127.0.0.1:7897"
}

# --------- 这是原来的单次预测接口 (保持不变) ---------
class AIAdviceRequest(BaseModel):
    peak_hour: int
    max_volume: int

@app.post("/ai_advice")
def get_gemini_advice(req: AIAdviceRequest):
    try:
        prompt = (
            f"你是一个智慧停车系统的 AI 运营专家。当前系统预测到在 {req.peak_hour}:00 "
            f"将达到车流顶峰（预计 {req.max_volume} 辆车）。请给出一段专业、极其简洁的运营建议 "
            f"（80字以内），包含调价建议和车辆分流方案。直接输出内容，不要说废话。"
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, proxies=PROXIES, timeout=15.0, verify=False)
        
        if response.status_code != 200:
            return {"advice": f"🚨 请求被拒绝了！状态码：{response.status_code}。具体原因：{response.text}"}
        
        result_data = response.json()
        real_advice = result_data['candidates'][0]['content']['parts'][0]['text']
        return {"advice": real_advice}
    except Exception as e:
        return {"advice": f"🚨 抓到真凶了！底层报错信息是：【{str(e)}】"}

# --------- 🚀 【新增】：多轮对话记忆接口 ---------
class ChatMessage(BaseModel):
    role: str   # 'user' 或者是 'model'
    text: str

class ChatRequest(BaseModel):
    history: List[ChatMessage] # 接收历史聊天记录
    message: str               # 用户最新的问题

@app.post("/ai_chat")
def get_gemini_chat(req: ChatRequest):
    try:
        # 1. 组装符合 Gemini 规范的历史上下文记忆
        contents = []
        for msg in req.history:
            contents.append({
                "role": msg.role,
                "parts": [{"text": msg.text}]
            })
        
        # 2. 把用户刚发送的新问题追加到最后
        contents.append({
            "role": "user",
            "parts": [{"text": req.message}]
        })
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": contents}
        
        # 发送携带记忆的请求
        response = requests.post(url, json=payload, proxies=PROXIES, timeout=20.0, verify=False)
        
        if response.status_code != 200:
            return {"reply": f"🚨 对话请求被拒绝！状态码：{response.status_code}。具体原因：{response.text}"}
        
        result_data = response.json()
        real_reply = result_data['candidates'][0]['content']['parts'][0]['text']
        
        return {"reply": real_reply}
        
    except Exception as e:
        return {"reply": f"🚨 网络通信异常或超时，错误详情：{str(e)}"}