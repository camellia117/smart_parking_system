from faker import Faker
import random
from datetime import timedelta
from backend.database import SessionLocal
from backend.models import ParkingRecord
from backend.database import engine
from backend.models import Base

# 创建数据表（关键一步）
Base.metadata.create_all(bind=engine)

fake = Faker()

db = SessionLocal()

for i in range(200):

    start = fake.date_time_this_year()

    end = start + timedelta(hours=random.randint(1,5))

    fee = random.randint(5,50)

    record = ParkingRecord(

        user_id=random.randint(1,10),

        lot_id=random.randint(1,5),

        enter_time=start,

        leave_time=end,

        fee=fee
    )

    db.add(record)

db.commit()

print("数据生成完成")