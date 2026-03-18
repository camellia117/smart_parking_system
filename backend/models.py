from backend.database import Base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    car_number = Column(String)
    phone = Column(String)


class ParkingLot(Base):

    __tablename__ = "parking_lots"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    location = Column(String)
    total_spaces = Column(Integer)
    price_per_hour = Column(Float)
    available_spaces = Column(Integer)  


# 修改 backend/models.py 增加特征字段
class ParkingRecord(Base):
    __tablename__ = "parking_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    lot_id = Column(Integer)
    enter_time = Column(DateTime)
    # 新增：是否为周末 (0或1)
    is_weekend = Column(Integer, default=0) 
    # 新增：天气状况 (0:晴, 1:雨/雪)
    weather_type = Column(Integer, default=0) 
    leave_time = Column(DateTime, nullable=True) 
    fee = Column(Float)
    
    # 修改 backend/models.py，在最下面追加
class SystemUser(Base):
    __tablename__ = "system_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)  # 实际项目中应存储加密后的哈希值
    role = Column(String) # root, dev, admin, screen 等
    phone = Column(String, unique=True, index=True, nullable=True) # 新增手机号字段