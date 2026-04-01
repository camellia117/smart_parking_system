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
import google.generativeai as genai
from pydantic import BaseModel

app = FastAPI(title="AI-Parking 智能停车系统 API")

# ====== 全局变量：临时存储验证码 ======
mock_verification_codes = {} 
mock_captchas = {}           
mock_login_sms_codes = {}    

# ====== CORS 跨域配置 ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

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
#             【新增】车场与计费规则管理 (ParkingLot 表)
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
    """获取所有停车场及其计费信息"""
    return db.query(models.ParkingLot).order_by(models.ParkingLot.id.desc()).all()

@app.post("/lots")
def create_lot(lot: LotCreate, db: Session = Depends(get_db)):
    """新增一个停车场"""
    new_lot = models.ParkingLot(
        name=lot.name, 
        location=lot.location, 
        total_spaces=lot.total_spaces, 
        price_per_hour=lot.price_per_hour,
        available_spaces=lot.total_spaces  # 初始空余车位等于总车位
    )
    db.add(new_lot)
    db.commit()
    db.refresh(new_lot)
    return new_lot

@app.put("/lots/{lot_id}")
def update_lot(lot_id: int, lot_data: LotUpdate, db: Session = Depends(get_db)):
    """动态修改计费规则和总车位数"""
    lot = db.query(models.ParkingLot).filter(models.ParkingLot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="未找到该车场")
    
    # 计算车位差值，同步更新剩余可用车位
    diff = lot_data.total_spaces - lot.total_spaces
    lot.total_spaces = lot_data.total_spaces
    lot.available_spaces = max(0, lot.available_spaces + diff)
    
    lot.price_per_hour = lot_data.price_per_hour
    db.commit()
    return {"message": "车场配置更新成功"}

@app.delete("/lots/{lot_id}")
def delete_lot(lot_id: int, db: Session = Depends(get_db)):
    """下线并删除车场"""
    lot = db.query(models.ParkingLot).filter(models.ParkingLot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="未找到该车场")
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
    if not owner:
        raise HTTPException(status_code=404, detail="未找到该车主记录")
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
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    if user.phone:
         db_phone = db.query(models.SystemUser).filter(models.SystemUser.phone == user.phone).first()
         if db_phone:
             raise HTTPException(status_code=400, detail="Phone number already registered")

    new_user = models.SystemUser(username=user.username, password=user.password, role=user.role, phone=user.phone)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/system_users/")
def get_system_users(skip: int = 0, limit: int = 100, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.SystemUser)
    if search:
        query = query.filter(
            (models.SystemUser.username.contains(search)) |
            (models.SystemUser.phone.contains(search))
        )
    return query.offset(skip).limit(limit).all()

@app.delete("/system_users/{user_id}")
def delete_system_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.SystemUser).filter(models.SystemUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "root":
         raise HTTPException(status_code=400, detail="Cannot delete root user")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@app.put("/system_users/")
def update_system_user(user_data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(models.SystemUser).filter(models.SystemUser.id == user_data.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.username != user_data.username:
        if db.query(models.SystemUser).filter(models.SystemUser.username == user_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
    if user.phone != user_data.phone:
        if db.query(models.SystemUser).filter(models.SystemUser.phone == user_data.phone).first():
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
    if not user:
        raise HTTPException(status_code=404, detail="User with this phone not found")
    
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
        user = db.query(models.SystemUser).filter(
            models.SystemUser.username == req.username,
            models.SystemUser.password == req.password
        ).first()
        if not user:
            raise HTTPException(status_code=401, detail="账号或密码错误")
        if not user.phone:
            raise HTTPException(status_code=400, detail="该账号未绑定手机号，无法接收验证码")
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
    return {
        "message": "Login successful", 
        "role": user.role, 
        "username": user.username, 
        "phone": user.phone
    }


# 1. 配置 API Key
GEMINI_API_KEY = "AIzaSyAbD0drnrMc6ZWZtKcT90kjyTXRsizg3cI"
genai.configure(api_key=GEMINI_API_KEY)

# 2. 初始化模型 (推荐使用 1.5-flash，速度最快且适合毕设)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# 3. 定义请求模型
class AIAdviceRequest(BaseModel):
    peak_hour: int      # 预测的高峰时段
    max_volume: int     # 预测的最高车辆数

# 4. 编写真实的 AI 决策接口
@app.post("/ai_advice")
async def get_gemini_advice(req: AIAdviceRequest):
    try:
        #  Prompt (提示词)
        prompt = (
            f"你是一个智慧停车系统的 AI 运营专家。当前系统预测到在 {req.peak_hour}:00 "
            f"将达到车流顶峰（预计 {req.max_volume} 辆车）。请给出一段专业、简洁的运营建议 "
            f"（80字以内），包含调价建议和车辆分流方案。直接输出内容，不要寒暄。"
        )
        
        # 真正向云端请求回答
        response = gemini_model.generate_content(prompt)
        
        return {"advice": response.text}
    except Exception as e:
        # 容错处理：如果网络不通，返回预设的专家规则
        return {"advice": "系统检测到车流激增，建议立即启动动态调价机制，并在入口大屏显示周边停车场剩余车位，引导非月租车辆错峰入场。"}