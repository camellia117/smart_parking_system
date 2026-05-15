import sys
import os
import pandas as pd
from sqlalchemy.exc import IntegrityError

# 确保脚本能找到 backend 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal, engine
from backend.models import Base, ParkingLot

def init_db():
    print("正在初始化数据库结构（全字段模式）...")
    Base.metadata.create_all(bind=engine)

def safe_int(val):
    """严谨的数字转换：防止 Excel 中的空值或非数字字符导致程序崩溃"""
    try:
        return int(float(val)) if pd.notna(val) and str(val).strip() != "" else 0
    except ValueError:
        return 0

def import_all_columns(excel_path):
    db = SessionLocal()
    try:
        print(f"开始读取全量 Excel 数据文件: {excel_path}")
        df = pd.read_excel(excel_path)
        df = df.fillna("") # 空值填充
        
        success_count = 0
        skip_count = 0
        
        for index, row in df.iterrows():
            platform_id_val = str(row.get('id', '')).strip()
            
            # 【新增防御 1】过滤空数据行
            if not platform_id_val or platform_id_val == "nan":
                continue
                
            # 【新增防御 2】检查数据库是否已存在该 ID (防止 UNIQUE 报错)
            existing_lot = db.query(ParkingLot).filter(ParkingLot.platform_id == platform_id_val).first()
            if existing_lot:
                skip_count += 1
                continue

            # 构建新的停车场对象
            lot = ParkingLot(
                platform_id=platform_id_val,
                parking_id=str(row.get('parking_id', '')),
                parking_name=str(row.get('parking_name', '')),
                address=str(row.get('address', '')),
                district_id=str(row.get('district_id', '')),
                parking_nature=str(row.get('parking_nature', '')),
                
                # 数字型字段安全提取
                total_berth=safe_int(row.get('total_berth')),
                battery_berth=safe_int(row.get('battery_berth')),
                real_berth=safe_int(row.get('real_berth')),
                month_berth=safe_int(row.get('month_berth')),
                nobarry_berth=safe_int(row.get('nobarry_berth')),
                transfer_berth=safe_int(row.get('transfer_berth')),
                
                # 文本型字段提取
                living_time=str(row.get('living_time', '')),
                mark_expiry=str(row.get('mark_expiry', '')),
                server_time=str(row.get('server_time', '')),
                company_manage=str(row.get('company_manage', '')),
                jhpt_update_flag=str(row.get('jhpt_update_flag', '')),
                data_time=str(row.get('data_time', '')),
                parking_area=str(row.get('parking_area', '')),
                parking_estates=str(row.get('parking_estates', '')),
                managecode_id=str(row.get('managecode_id', '')),
                jhpt_delete=str(row.get('jhpt_delete', '')),
                parking_property=str(row.get('parking_property', '')),
                rent_expiry=str(row.get('rent_expiry', '')),
                complained_tel=str(row.get('complained_tel', '')),
                parking_status=str(row.get('parking_status', '')),
                jhpt_update_time=str(row.get('jhpt_update_time', '')),
                server_tel=str(row.get('server_tel', '')),
                estates_name=str(row.get('estates_name', '')),
                record_mark=str(row.get('record_mark', '')),
                server_type=str(row.get('server_type', ''))
            )
            
            db.add(lot)
            success_count += 1
            
            # 分批提交，提高速度并防止内存溢出
            if success_count > 0 and success_count % 200 == 0:
                db.commit()
                
        db.commit()
        print(f"✅ 导入完成！共成功新增 {success_count} 条数据，自动跳过了 {skip_count} 条重复/脏数据。")

    except Exception as e:
        db.rollback()
        print(f"❌ 导入过程中发生错误: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    
    # 动态获取当前脚本所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FILE_PATH = os.path.join(BASE_DIR, "公共停车场基础数据.xlsx")
    
    if os.path.exists(FILE_PATH):
        import_all_columns(FILE_PATH)
    else:
        print(f"报错：系统确实找不到文件 {FILE_PATH}，请检查该路径下文件是否存在。")