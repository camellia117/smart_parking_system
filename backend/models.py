from sqlalchemy import Column, Integer, String, Float, DateTime
from backend.database import Base



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


class ParkingRecord(Base):

    __tablename__ = "parking_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    lot_id = Column(Integer)
    enter_time = Column(DateTime)
    leave_time = Column(DateTime, nullable=True) 
    fee = Column(Float)