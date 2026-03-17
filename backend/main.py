from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel  # <--- 就是少了这一行！
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend import models

from backend.crud import get_all_records, get_all_lots 
from backend.analytics import statistics
from ai_prediction.predict import predict_day

app = FastAPI(title="Smart Parking System")

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

# 2. 定义前端传过来的登录数据格式
class LoginRequest(BaseModel):
    username: str
    password: str

# 3. 登录接口
@app.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # 特殊后门：系统刚初始化没数据时，允许万能超管登录以方便调试
    if req.username == "root" and req.password == "123456":
        return {"success": True, "role": "dev", "message": "超管登录"}
        
    user = db.query(models.SystemUser).filter(
        models.SystemUser.username == req.username, 
        models.SystemUser.password == req.password
    ).first()
    
    if user:
        return {"success": True, "role": user.role, "message": "验证通过"}
    else:
        return {"success": False, "message": "账号或密码错误！"}