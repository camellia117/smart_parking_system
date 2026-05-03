from backend.database import Base
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String)
    car_number = Column(String)
    phone = Column(String)

class ParkingLot(Base):
    __tablename__ = "parking_lots"

    # 系统内部自增主键
    internal_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ---------------- 以下为全量映射你 Excel 里的 31 个字段 ----------------
    platform_id = Column(String, unique=True, index=True) # 对应CSV的 id
    parking_id = Column(String, index=True)               # 场库编号
    parking_name = Column(String)                         # 场库名称
    address = Column(String)                              # 场库地址
    district_id = Column(String, index=True)              # 行政区编号
    parking_nature = Column(String)                       # 场库类型
    
    # 泊位数量相关 (数值型)
    total_berth = Column(Integer, default=0)              # 泊位总数
    battery_berth = Column(Integer, default=0)            # 充电泊位数
    real_berth = Column(Integer, default=0)               # 时租泊位数
    month_berth = Column(Integer, default=0)              # 月租泊位数
    nobarry_berth = Column(Integer, default=0)            # 无障碍泊位数
    transfer_berth = Column(Integer, default=0)           # 换乘泊位数
    
    # 文本与属性相关 (字符型)
    living_time = Column(String)                          # 业务时间
    mark_expiry = Column(String)                          # 备案证有效期
    server_time = Column(String)                          # 全年服务时间
    company_manage = Column(String)                       # 业主单位名称
    jhpt_update_flag = Column(String)                     # 标志位
    data_time = Column(String)                            # 数据时间
    parking_area = Column(String)                         # 占地面积
    parking_estates = Column(String)                      # 产权性质
    managecode_id = Column(String)                        # 管理区域标识
    jhpt_delete = Column(String)                          # 删除位
    parking_property = Column(String)                     # 经营性质
    rent_expiry = Column(String)                          # 产权租赁时间
    complained_tel = Column(String)                       # 投诉电话
    parking_status = Column(String)                       # 经营状态
    jhpt_update_time = Column(String)                     # 时间戳
    server_tel = Column(String)                           # 服务电话
    estates_name = Column(String)                         # 产权方名称
    record_mark = Column(String)                          # 备案证号
    server_type = Column(String)                          # 服务时间
    
    # ---------------- 动态业务字段 (Excel中没有，为系统运行预留) ----------------
    available_spaces = Column(Integer, default=0)         # 实时空余车位(后续API更新)
    price_per_hour = Column(Float, default=0.0)           # 每小时价格


class ParkingRecord(Base):
    __tablename__ = "parking_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    lot_id = Column(Integer)
    enter_time = Column(DateTime)
    is_weekend = Column(Integer, default=0) 
    weather_type = Column(Integer, default=0) 
    leave_time = Column(DateTime, nullable=True) 
    fee = Column(Float)
    
class SystemUser(Base):
    __tablename__ = "system_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)  
    role = Column(String) 
    phone = Column(String, unique=True, index=True, nullable=True)
    
class WeatherHistory(Base):
    __tablename__ = "weather_history"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)  # 存储日期字符串，如 '2024-01-18'
    weather_text = Column(String)      # 存储 '多云到阴局部地区有小雨'
    is_rainy = Column(Integer)         # 预处理好的数字特征：1为雨雪，0为晴阴