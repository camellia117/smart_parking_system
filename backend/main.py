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

@app.get("/lots")  
def lots():
    return get_all_lots()

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
#             【新增】客户与白名单车辆管理 (User 表)
# =========================================================
class CarOwnerCreate(BaseModel):
    username: str
    car_number: str
    phone: str

@app.get("/car_owners/")
def get_car_owners(db: Session = Depends(get_db)):
    """获取所有已登记的车主和车辆信息"""
    return db.query(models.User).order_by(models.User.id.desc()).all()

@app.post("/car_owners/")
def create_car_owner(owner: CarOwnerCreate, db: Session = Depends(get_db)):
    """新增白名单/月租车辆"""
    # 检查车牌是否已经登记过
    if db.query(models.User).filter(models.User.car_number == owner.car_number).first():
        raise HTTPException(status_code=400, detail="该车牌号已存在，请勿重复登记")
    
    new_owner = models.User(username=owner.username, car_number=owner.car_number, phone=owner.phone)
    db.add(new_owner)
    db.commit()
    db.refresh(new_owner)
    return new_owner

@app.delete("/car_owners/{owner_id}")
def delete_car_owner(owner_id: int, db: Session = Depends(get_db)):
    """移除车主信息"""
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