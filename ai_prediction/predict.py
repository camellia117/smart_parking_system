import joblib
import pandas as pd

model = joblib.load("ai_prediction/model.pkl")

def predict_day():

    hours = list(range(24))

    df = pd.DataFrame({"hour":hours})

    pred = model.predict(df)

    result = []

    for h,p in zip(hours,pred):

        result.append({
            "hour":h,
            "predicted_cars":int(p)
        })

    return result