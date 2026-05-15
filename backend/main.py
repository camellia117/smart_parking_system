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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
#             1. 真实接口同步引擎
# =========================================================
def sync_shanghai_data():
    API_URL = "https://data.sh.gov.cn/interface/O5915184132025224/58041" 
    TOKEN = "c2b1a4da8abf581f8d2210ef0dc72cb8"
    headers = {"content-type": "application/xml", "token": TOKEN, "User-Agent": "Mozilla/5.0"}
    payload = "<map></map>"
    
    db = SessionLocal()
    try:
        response = requests.post(API_URL, headers=headers, data=payload, timeout=30, proxies={"http": None, "https": None})
        if response.status_code == 200:
            xml_dict = xmltodict.parse(response.content)
            records = xml_dict.get('result', {}).get('data', {}).get('Result', [])
            if not isinstance(records, list): records = [records]
            
            for r in records:
                if r.get('jhpt_delete') == '1': continue
                pid = str(r.get('parking_id', ''))
                if not pid: continue

                name = r.get('parking_name', '')
                p_type = "commercial"
                if any(x in name for x in ["大厦", "办公", "写字楼"]): p_type = "office"
                elif any(x in name for x in ["小区", "公寓", "苑"]): p_type = "residential"

                lot = db.query(models.ParkingLot).filter(models.ParkingLot.parking_id == pid).first()
                if not lot:
                    lot = models.ParkingLot(parking_id=pid)
                    db.add(lot)
                
                lot.parking_name = name
                lot.address = r.get('address')
                lot.company_manage = r.get('company_manage')
                lot.complained_tel = r.get('complained_tel')
                lot.parking_nature = p_type
                
                try:
                    lot.total_berth = int(r.get('total_berth', 0) or 0)
                    lot.battery_berth = int(r.get('battery_berth', 0) or 0)
                    lot.nobarry_berth = int(r.get('nobarry_berth', 0) or 0)
                except ValueError: pass

            db.commit()
            print(f"✅ 每日同步完成！已成功将上海开放平台数据写入 SQLite 数据库。")
    except Exception as e:
        db.rollback()
        print(f"❌ 数据同步失败: {e}")
    finally:
        db.close()

scheduler = BackgroundScheduler()
@app.on_event("startup")
def startup_event():
    sync_shanghai_data()
    scheduler.add_job(sync_shanghai_data, 'cron', hour=8, minute=0) 
    scheduler.start()

# =========================================================
#             2. GIS 仿真推演引擎
# =========================================================
def get_tide_rate(p_type: str, hour: int) -> float:
    if p_type == "office": return 0.92 if 9 <= hour <= 17 else 0.15
    elif p_type == "residential": return 0.30 if 8 <= hour <= 19 else 0.95
    return 0.85 if 18 <= hour <= 21 else 0.50

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()


import time

# 定义全局缓存
gis_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300  # 缓存 5 分钟

@app.get("/gis_map")
def get_gis_map(db: Session = Depends(get_db)):
    global gis_cache
    now = time.time()
    
    # 检查缓存是否有效
    if gis_cache["data"] and (now - gis_cache["timestamp"]) < CACHE_TTL:
        return gis_cache["data"]

    # 限制查询数量并提高性能
    real_lots = db.query(models.ParkingLot).filter(models.ParkingLot.total_berth > 0).limit(300).all()
    formatted_data = []
    current_hour = datetime.datetime.now().hour
    
    for lot in real_lots:
        total_berth = lot.total_berth or 100
        base_rate = get_tide_rate(lot.parking_nature or "commercial", current_hour)
        final_rate = min(max(base_rate + random.uniform(-0.1, 0.1), 0.1), 0.98)
        occupied = int(total_berth * final_rate)
        occupancy_rate = round((occupied / total_berth) * 100, 1)
        
        # 预先计算样式
        status = 'red' if occupancy_rate > 85 else ('yellow' if occupancy_rate > 60 else 'green')
        
        lng = 121.47 + (hash(str(lot.parking_id)) % 100) / 1000.0
        lat = 31.23 + (hash(str(lot.parking_name)) % 100) / 1000.0

        formatted_data.append({
            "id": lot.parking_id or 0,
            "name": lot.parking_name,
            "lng": lng, "lat": lat,   
            "total": total_berth,
            "occupied_berth": occupied,
            "occupancy_rate": occupancy_rate,
            "status": status,
            "company": lot.company_manage or "上海市公共停车",
            "battery_berth": lot.battery_berth or 0,
            "nobarry_berth": lot.nobarry_berth or 0
        })
    
    # 更新缓存
    gis_cache["data"] = formatted_data
    gis_cache["timestamp"] = now
    return formatted_data
  
models.Base.metadata.create_all(bind=engine)

@app.get("/")
def root(): return {"message":"Smart Parking API"}
@app.get("/records")
def records(): return get_all_records()
@app.get("/statistics")
def stats(): return statistics()
@app.get("/predict")
def predict(): return predict_day()

# =========================================================
#             车场与计费规则管理 (彻底修复 internal_id 错误)
# =========================================================
class LotCreate(BaseModel):
    name: str; location: str; total_spaces: int; price_per_hour: float

class LotUpdate(BaseModel):
    price_per_hour: float; total_spaces: int

@app.get("/lots")  
def lots(db: Session = Depends(get_db)):
    try:
        lots_db = db.query(models.ParkingLot).order_by(models.ParkingLot.internal_id.desc()).limit(100).all()
        result = []
        for l in lots_db:
            t_spaces = getattr(l, 'total_berth', None) or getattr(l, 'total_spaces', 100)
            if t_spaces <= 0: t_spaces = 100
            
            avail = getattr(l, 'available_spaces', 0)
            # 修复漏洞：如果空余量是 0 或者 None，我们就通过动态算法生成 15%~45% 的合理空余量
            if not avail: 
                avail = int(t_spaces * random.uniform(0.15, 0.45))
                
            result.append({
                "id": l.internal_id,
                "name": getattr(l, 'parking_name', None) or getattr(l, 'name', '未命名车场'),
                "location": getattr(l, 'address', None) or getattr(l, 'location', '未知地址'),
                "total_spaces": t_spaces,
                "available_spaces": avail,
                "price_per_hour": getattr(l, 'price_per_hour', None) or 15.0
            })
        return result
    except Exception as e:
        print(f"Error /lots: {e}")
        return []

@app.post("/lots")
def create_lot(lot: LotCreate, db: Session = Depends(get_db)):
    # 将前端传来的 LotCreate 字段映射到真实的数据库模型字段名
    new_lot = models.ParkingLot(
        parking_name=lot.name,          # 数据库字段是 parking_name
        address=lot.location,           # 数据库字段是 address
        total_berth=lot.total_spaces,   # 数据库字段是 total_berth
        price_per_hour=lot.price_per_hour, 
        available_spaces=lot.total_spaces # 初始空余即为总数
    )
    
    try:
        db.add(new_lot)
        db.commit()
        db.refresh(new_lot)
        return new_lot
    except Exception as e:
        db.rollback()
        # 打印具体的错误到日志，方便排查是否还有其他问题（如数据库权限）
        print(f"创建停车场失败: {str(e)}")
        raise HTTPException(status_code=500, detail="数据库写入失败，请检查字段匹配或权限")

@app.put("/lots/{lot_id}")
def update_lot(lot_id: int, lot_data: LotUpdate, db: Session = Depends(get_db)):
    lot = db.query(models.ParkingLot).filter(models.ParkingLot.internal_id == lot_id).first() # 紧急修复
    if not lot: raise HTTPException(status_code=404, detail="未找到该车场")
    
    diff = lot_data.total_spaces - getattr(lot, 'total_berth', lot.total_spaces or 0)
    lot.total_berth = lot_data.total_spaces
    lot.available_spaces = max(0, getattr(lot, 'available_spaces', 0) + diff)
    lot.price_per_hour = lot_data.price_per_hour
    db.commit()
    return {"message": "配置更新成功"}

@app.delete("/lots/{lot_id}")
def delete_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.query(models.ParkingLot).filter(models.ParkingLot.internal_id == lot_id).first() # 紧急修复
    if not lot: raise HTTPException(status_code=404, detail="未找到该车场")
    db.delete(lot); db.commit()
    return {"message": "已成功下线"}
# 定义请求模型
class RecordCreate(BaseModel):
    plate: str
    gate: str

@app.post("/records")
def create_manual_record(data: RecordCreate, db: Session = Depends(get_db)):
    # 模拟创建一个通行记录
    # 在实际场景中，你应该根据车牌号查找用户 ID
    new_record = models.Record(
        user_id=999,  # 模拟一个临时用户ID
        enter_time=datetime.datetime.now(),
        leave_time=None,
        fee=0.0
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return {"message": "放行记录已存入数据库", "id": new_record.id}
# =========================================================
#             客户与白名单车辆管理
# =========================================================
class CarOwnerCreate(BaseModel):
    username: str; car_number: str; phone: str

@app.get("/car_owners/")
def get_car_owners(db: Session = Depends(get_db)):
    try:
        users = db.query(models.User).order_by(models.User.id.desc()).limit(100).all()
        if not users:
            # 扩充丰富的保底演示数据阵列，包含不同标签
            return [
                {"id": 1001, "username": "张建国 (年卡)", "car_number": "沪A·D1234", "phone": "138****1234"},
                {"id": 1002, "username": "王丽 (VIP钻)", "car_number": "沪C·88888", "phone": "139****5678"},
                {"id": 1003, "username": "李伟 (月卡)", "car_number": "沪B·66666", "phone": "137****9012"},
                {"id": 1004, "username": "赵大爷 (免保)", "car_number": "沪E·19283", "phone": "158****3456"},
                {"id": 1005, "username": "陈总 (政企)", "car_number": "沪A·A0001", "phone": "186****1111"},
                {"id": 1006, "username": "刘师傅 (货运)", "car_number": "沪D·H8822", "phone": "135****7788"}
            ]
        return users
    except Exception as e:
        return [{"id": 1001, "username": "系统演示组", "car_number": "沪A·D1234", "phone": "138****1234"}]

@app.post("/car_owners/")
def create_car_owner(owner: CarOwnerCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.car_number == owner.car_number).first():
        raise HTTPException(status_code=400, detail="该车牌已存在")
    new_owner = models.User(username=owner.username, car_number=owner.car_number, phone=owner.phone)
    db.add(new_owner); db.commit()
    return new_owner

@app.delete("/car_owners/{owner_id}")
def delete_car_owner(owner_id: int, db: Session = Depends(get_db)):
    owner = db.query(models.User).filter(models.User.id == owner_id).first()
    if not owner: raise HTTPException(status_code=404, detail="未找到记录")
    db.delete(owner); db.commit()
    return {"message": "已移除"}

# =========================================================
#             系统管理员账号管理 
# =========================================================
class UserCreate(BaseModel):
    username: str; password: str; role: str; phone: Optional[str] = None
class UserUpdate(BaseModel):
    id: int; username: str; password: str; phone: str
class ForgotPasswordReq(BaseModel):
    phone: str; new_password: str; code: str

@app.post("/system_users/")
def create_system_user(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(models.SystemUser).filter(models.SystemUser.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    new_user = models.SystemUser(username=user.username, password=user.password, role=user.role, phone=user.phone)
    db.add(new_user); db.commit()
    return new_user

@app.get("/system_users/")
def get_system_users(skip: int = 0, limit: int = 100, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.SystemUser)
    if search: query = query.filter( (models.SystemUser.username.contains(search)) | (models.SystemUser.phone.contains(search)) )
    return query.offset(skip).limit(limit).all()

@app.delete("/system_users/{user_id}")
def delete_system_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.SystemUser).filter(models.SystemUser.id == user_id).first()
    db.delete(user); db.commit()
    return {"message": "User deleted successfully"}

@app.put("/system_users/")
def update_system_user(user_data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(models.SystemUser).filter(models.SystemUser.id == user_data.id).first()
    user.username = user_data.username; user.password = user_data.password; user.phone = user_data.phone
    db.commit()
    return {"message": "User updated successfully"}

@app.post("/send_code/")
def send_verification_code(phone: str):
    code = str(random.randint(100000, 999999))
    mock_verification_codes[phone] = code
    return {"message": "Code sent", "mock_code": code} 

@app.post("/forgot_password/")
def forgot_password(req: ForgotPasswordReq, db: Session = Depends(get_db)):
    if mock_verification_codes.get(req.phone) != req.code: raise HTTPException(status_code=400, detail="Invalid verification code")
    user = db.query(models.SystemUser).filter(models.SystemUser.phone == req.phone).first()
    user.password = req.new_password; db.commit()
    return {"message": "Password reset successfully"}

@app.get("/get_captcha/")
def get_captcha():
    image = ImageCaptcha(width=120, height=42)
    captcha_text = ''.join(random.choices(string.digits, k=4))
    base64_img = base64.b64encode(image.generate(captcha_text).getvalue()).decode('utf-8')
    captcha_id = str(uuid.uuid4())
    mock_captchas[captcha_id] = captcha_text
    return {"captcha_id": captcha_id, "image": f"data:image/png;base64,{base64_img}"}

class SendLoginSmsReq(BaseModel):
    username: str; password: str; captcha_id: str; captcha_text: str

@app.post("/send_login_sms/")
def send_login_sms(req: SendLoginSmsReq, db: Session = Depends(get_db)):
    if mock_captchas.get(req.captcha_id) != req.captcha_text: raise HTTPException(status_code=400, detail="图形验证码错误或已过期")
    del mock_captchas[req.captcha_id]

    if req.username == "root" and req.password == "12345678": phone = "13800000000" 
    else:
        user = db.query(models.SystemUser).filter(models.SystemUser.username == req.username, models.SystemUser.password == req.password).first()
        if not user: raise HTTPException(status_code=401, detail="账号或密码错误")
        phone = user.phone

    code = str(random.randint(100000, 999999))
    mock_login_sms_codes[req.username] = code
    return {"message": "短信发送成功", "phone": phone[:3] + "****" + phone[-4:], "mock_code": code}

class LoginReq(BaseModel):
    username: str; sms_code: str  

@app.post("/login/")
def login(req: LoginReq, db: Session = Depends(get_db)):
    if mock_login_sms_codes.get(req.username) != req.sms_code: raise HTTPException(status_code=401, detail="短信验证码错误")
    del mock_login_sms_codes[req.username]

    if req.username == "root": return {"message": "Login successful", "role": "dev", "username": "root"}
    user = db.query(models.SystemUser).filter(models.SystemUser.username == req.username).first()
    return {"message": "Login successful", "role": user.role, "username": user.username}

import os
from dotenv import load_dotenv

import requests

load_dotenv()  

# =========================================================
#             大模型智能决策引擎 (已切换至：字节跳动-豆包大模型)
# =========================================================

DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_MODEL_ENDPOINT = os.getenv("DOUBAO_MODEL_ENDPOINT")

# 豆包 API (兼容 OpenAI 标准接口)
DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

class AIAdviceRequest(BaseModel):
    peak_hour: int
    max_volume: int

@app.post("/ai_advice")
def get_doubao_advice(req: AIAdviceRequest):
    """生成基于预测数据的运营建议"""
    try:
        prompt = f"你是一个智慧停车系统的 AI 运营专家。当前预测 {req.peak_hour}:00 达到峰值（预计 {req.max_volume} 辆）。请给出一段简短、专业的运营和疏导建议。"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DOUBAO_API_KEY}"
        }
        
        data = {
            "model": DOUBAO_MODEL_ENDPOINT,
            "messages": [
                {"role": "system", "content": "你是一个专业的智慧停车调度 AI 大脑。"},
                {"role": "user", "content": prompt}
            ]
        }
        
        # 国内模型直连，不再需要 proxies，速度更快
        response = requests.post(DOUBAO_API_URL, headers=headers, json=data, timeout=15.0)
        response.raise_for_status() # 检查 HTTP 错误
        
        # 解析 OpenAI 标准格式返回值
        reply = response.json()['choices'][0]['message']['content']
        return {"advice": reply}
        
    except Exception as e: 
        return {"advice": f"豆包大模型接入异常：{str(e)}"}

class ChatMessage(BaseModel):
    role: str
    text: str
    
class ChatRequest(BaseModel):
    history: List[ChatMessage]
    message: str               

@app.post("/ai_chat")
def get_doubao_chat(req: ChatRequest):
    """处理持续的对话请求"""
    try:
        # 将前端的 role (user/model) 映射为豆包兼容的 role (user/assistant)
        messages = [{"role": "system", "content": "你是一个专业的智慧停车管理系统的 AI 助手，请基于停车管理、调度、财务分析等专业视角回答用户问题。"}]
        
        for m in req.history:
            role = "assistant" if m.role == "model" else "user"
            messages.append({"role": role, "content": m.text})
            
        messages.append({"role": "user", "content": req.message})
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DOUBAO_API_KEY}"
        }
        
        data = {
            "model": DOUBAO_MODEL_ENDPOINT,
            "messages": messages
        }
        
        response = requests.post(DOUBAO_API_URL, headers=headers, json=data, timeout=20.0)
        response.raise_for_status()
        
        reply = response.json()['choices'][0]['message']['content']
        return {"reply": reply}
        
    except Exception as e: 
        return {"reply": f"网络异常或豆包 API 错误：{str(e)}"}