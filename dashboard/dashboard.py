import streamlit as st
import requests

st.title("智慧停车数据分析大屏")

data = requests.get("http://127.0.0.1:8000/statistics").json()

st.metric("停车记录",data["records"])
st.metric("总收入",data["total_revenue"])
st.metric("平均停车时长",data["avg_parking_time"])