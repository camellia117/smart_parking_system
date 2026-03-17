from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel  
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend import models
from backend.crud import get_all_records, get_all_lots 
from backend.analytics import statistics
from ai_prediction.predict import predict_day
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.database import SessionLocal, engine
from backend import models

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

# 下面是你原有的路由代码...

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
# ====== 【更新】连接真实数据库的登录接口 ======
@app.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # 1. 保留一个特殊的“后门（root）”账号：
    # 因为系统刚初始化时数据库里没有任何账号，你需要一个超级账号先登进去，
    # 进入 dashboard 页面后，再通过表单创建真实的员工账号。
    if req.username == "root" and req.password == "123456":
        return {"success": True, "role": "dev", "message": "系统初始超管登录"}
        
    # 2. 从真实的数据库表 (SystemUser) 中查询账号和密码
    user = db.query(models.SystemUser).filter(
        models.SystemUser.username == req.username, 
        models.SystemUser.password == req.password
    ).first()
    
    # 3. 判断查询结果并返回前端需要的格式
    if user:
        # 如果能在数据库里找到这个人，就返回他真正的角色权限 (user.role)
        return {"success": True, "role": user.role, "message": "验证通过"}
    else:
        # 找不到人或者密码错误
        return {"success": False, "message": "账号或密码错误！请检查输入。"}