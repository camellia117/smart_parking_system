import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from backend.database import SessionLocal
from backend.models import ParkingRecord
import joblib

db = SessionLocal()

records = db.query(ParkingRecord).all()

data = []

for r in records:

    hour = r.enter_time.hour

    data.append({"hour":hour})

df = pd.DataFrame(data)

hourly = df.groupby("hour").size().reset_index(name="count")

X = hourly[["hour"]]

y = hourly["count"]

model = RandomForestRegressor()

model.fit(X,y)

joblib.dump(model,"ai_prediction/model.pkl")