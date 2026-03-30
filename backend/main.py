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
app = FastAPI(title="AI-Parking 智能停车系统 API")

# ====== 全局变量：临时存储验证码 ======
# 实际生产环境中，请将这些存入 Redis 并设置过期时间
mock_verification_codes = {} # 用于找回密码
mock_captchas = {}           # 用于暂存图形验证码: {captcha_id: captcha_text}
mock_login_sms_codes = {}    # 用于暂存登录短信验证码: {username: sms_code}
# ====== 【新增】CORS 跨域配置 ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有来源，生产环境建议改成具体的域名/IP
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法 (GET, POST 等)
    allow_headers=["*"],  # 允许所有请求头
)
# ===================================

models.Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message":"Smart Parking API"}

@app.get("/records")
def records():
    return get_all_records()

@app.get("/lots")  
def lots():
    return get_all_lots()

@app.get("/statistics")
def stats():
    return statistics()

@app.get("/predict")
def predict():
    return predict_day()

# 1. 数据库依赖注入函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    
# 定义 Pydantic 模型用于接收数据
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

# 临时存储验证码（实际项目应使用 Redis 等）
mock_verification_codes = {}

@app.post("/system_users/")
def create_system_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.SystemUser).filter(models.SystemUser.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # 检查手机号是否已被使用
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
        # 支持按用户名或手机号模糊查询
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
    # 禁止删除 root 账号
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
    
    # 如果修改了用户名或手机号，检查是否与其他账号冲突
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
    # 模拟发送验证码
    code = str(random.randint(100000, 999999))
    mock_verification_codes[phone] = code
    print(f"【模拟短信】发送给 {phone} 的验证码是: {code}")
    return {"message": "Code sent", "mock_code": code} # 仅为测试方便返回，实际不应返回

@app.post("/forgot_password/")
def forgot_password(req: ForgotPasswordReq, db: Session = Depends(get_db)):
    if req.phone not in mock_verification_codes or mock_verification_codes[req.phone] != req.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    user = db.query(models.SystemUser).filter(models.SystemUser.phone == req.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this phone not found")
    
    user.password = req.new_password
    db.commit()
    # 用完后清除验证码
    del mock_verification_codes[req.phone]
    return {"message": "Password reset successfully"}

# =========================================================
#                    【新增】安全登录核心逻辑
# =========================================================

@app.get("/get_captcha/")
def get_captcha():
    """1. 生成图形验证码并返回 Base64 图片"""
    image = ImageCaptcha(width=120, height=42)
    # 随机生成 4 位数字字母组合
    captcha_text = ''.join(random.choices(string.digits, k=4))
    data = image.generate(captcha_text)
    base64_img = base64.b64encode(data.getvalue()).decode('utf-8')
    
    # 生成唯一 ID 以追踪此验证码
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
    """2. 校验账号密码及图形验证码，通过后发送短信"""
    # [校验一]：检查图形验证码
    if req.captcha_id not in mock_captchas or mock_captchas[req.captcha_id] != req.captcha_text:
        raise HTTPException(status_code=400, detail="图形验证码错误或已过期")
    # 用完即焚，防止重复使用
    del mock_captchas[req.captcha_id]

    # [校验二]：检查账号和密码
    phone = None
    if req.username == "root" and req.password == "12345678":
        phone = "13800000000" # 假设的 root 手机号，方便演示
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

    # [执行发送]：生成并下发短信验证码
    code = str(random.randint(100000, 999999))
    mock_login_sms_codes[req.username] = code
    print(f"【模拟登录短信】发送给 {req.username} (手机: {phone}) 的验证码是: {code}")
    
    # 安全起见，只返回脱敏的手机号给前端显示
    masked_phone = phone[:3] + "****" + phone[-4:]
    return {"message": "短信发送成功", "phone": masked_phone, "mock_code": code}

class LoginReq(BaseModel):
    username: str
    sms_code: str  # 不再传密码，改传短信验证码

@app.post("/login/")
def login(req: LoginReq, db: Session = Depends(get_db)):
    """3. 最终登录校验：核对短信验证码"""
    if req.username not in mock_login_sms_codes or mock_login_sms_codes[req.username] != req.sms_code:
        raise HTTPException(status_code=401, detail="短信验证码错误或已过期")
    
    # 验证成功，清理验证码缓存
    del mock_login_sms_codes[req.username]

    # 颁发登录凭证
    if req.username == "root":
        return {"message": "Login successful", "role": "dev", "username": "root", "phone": "13800000000"}

    user = db.query(models.SystemUser).filter(models.SystemUser.username == req.username).first()
    return {
        "message": "Login successful", 
        "role": user.role, 
        "username": user.username, 
        "phone": user.phone
    }