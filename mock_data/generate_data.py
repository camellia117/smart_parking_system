import sys
import os
import random
from datetime import timedelta
from faker import Faker

# 将项目根目录添加到系统路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, engine
from backend.models import Base, ParkingRecord, User

def generate_mock_data(num_records=200):
    print("正在检查并创建数据库表结构...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 核心改造 1：每次生成前清空旧流水，保证数据幂等性，防止无限叠加
        print("正在清理旧的虚拟流水数据...")
        db.query(ParkingRecord).delete()
        db.commit()

        # 核心改造 2：使用中文 Faker 显得更真实
        fake = Faker('zh_CN')
        print(f"开始生成 {num_records} 条带有环境特征的新流水...")

        for i in range(num_records):
            start = fake.date_time_this_year()
            duration_hours = random.randint(1, 5)
            end = start + timedelta(hours=duration_hours)
            fee = duration_hours * random.randint(5, 15)

            # 核心改造 3：根据真实时间自动计算是否周末
            is_weekend = 1 if start.weekday() >= 5 else 0
            # 权重随机生成天气：80% 晴天(0)，20% 雨雪(1)
            weather_type = random.choices([0, 1], weights=[0.8, 0.2])[0]

            record = ParkingRecord(
                user_id=random.randint(1, 10),
                lot_id=random.randint(1, 5),
                enter_time=start,
                leave_time=end,
                is_weekend=is_weekend,       # 注入 AI 预测所需特征
                weather_type=weather_type,   # 注入 AI 预测所需特征
                fee=float(fee)
            )
            db.add(record)

            # 优化内存：每 50 条提交一次事务
            if i > 0 and i % 50 == 0:
                db.commit()

        db.commit()
        print("✅ 数据生成与特征注入全部完成！")

    except Exception as e:
        db.rollback()
        print(f"❌ 数据生成失败，已回滚: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    generate_mock_data(200)