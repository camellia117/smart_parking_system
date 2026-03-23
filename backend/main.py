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

app = FastAPI(title="AI-Parking 智能停车系统 API")

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

# ====== 唯一的、清理后的登录接口 ======
class LoginReq(BaseModel):
    username: str
    password: str

@app.post("/login/")
def login(req: LoginReq, db: Session = Depends(get_db)):
    # 1. 拦截检查：设置 root 账号和 12345678 密码，强制返回 dev 角色
    if req.username == "root" and req.password == "12345678":
        return {
            "message": "Login successful", 
            "role": "dev", 
            "username": "root", 
            "phone": None
        }

    # 2. 普通用户的真实数据库校验逻辑
    user = db.query(models.SystemUser).filter(
        models.SystemUser.username == req.username,
        models.SystemUser.password == req.password
    ).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    return {
        "message": "Login successful", 
        "role": user.role, 
        "username": user.username, 
        "phone": user.phone
    }