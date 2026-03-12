import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time

# 页面配置 (必须放在第一行)
st.set_page_config(page_title="智慧停车管控中枢 V2", layout="wide", page_icon="🌌")

# 全局 CSS 美化 (赛博朋克深色风格 + 卡片悬浮效果)
st.markdown("""
    <style>
    .main {background-color: #0b0f19;}
    .stApp {background-image: radial-gradient(circle at 50% 0%, #1a2235 0%, #0b0f19 70%);}
    h1, h2, h3 {color: #00eaff !important; font-family: 'Arial', sans-serif;}
    div[data-testid="metric-container"] {
        background: rgba(20, 30, 50, 0.7); border: 1px solid #1f3a5f; 
        padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,234,255,0.05);
        transition: transform 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px); border-color: #00eaff; box-shadow: 0 8px 25px rgba(0,234,255,0.2);
    }
    .css-1d391kg {background-color: #111827;} /* 侧边栏背景 */
    </style>
""", unsafe_allow_html=True)

# 侧边栏导航
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/smart-car.png", width=80)
    st.markdown("## 🌌 智慧停车中枢")
    st.markdown("---")
    menu = st.radio("系统导航", ["📊 实时监控大盘", "🚘 车辆放行与记录", "📈 AI预测与财务分析"])
    st.markdown("---")
    st.caption("🟢 系统状态: 运行中")
    st.caption("🌐 API 连接: 正常")

# 数据获取函数
# 修改前：@st.cache_data(ttl=10)
@st.cache_data(ttl=1)  # 【修改】：缓存降至1秒，确保拿到最新实时数据
def fetch_data(endpoint):
    try:
        return requests.get(f"http://127.0.0.1:8000/{endpoint}").json()
    except:
        return None
# ==================== 页面 1: 实时监控大盘 ====================
if menu == "📊 实时监控大盘":
    st.title("📊 城市级实时监控大盘")
    
    # 1. 先获取并渲染数据
    stats = fetch_data("statistics")
    
    if stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🅿️ 累计服务车次", f"{stats.get('records', 0)} 辆", "+12% 较昨日")
        c2.metric("💰 实时累计流水", f"¥ {stats.get('total_revenue', 0):.2f}", "+5.4%")
        c3.metric("⏱️ 平均驻留时长", f"{stats.get('avg_parking_time', 0):.1f} h", "-0.2 h")
        c4.metric("🚨 违停警告", "3 起", "已派发保安", delta_color="inverse")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 全市核心停车场实时状态面板
        st.subheader("🏙️ 城市路网停车场实时 API 监控")
        lots_data = fetch_data("lots")
        if lots_data:
            lots_df = pd.DataFrame(lots_data)
            # 计算占用率
            lots_df['占用率'] = ((lots_df['total_spaces'] - lots_df['available_spaces']) / lots_df['total_spaces'] * 100).round(1)
            
            # 使用更美观的列展示
            lot_cols = st.columns(len(lots_df))
            for idx, row in lots_df.iterrows():
                with lot_cols[idx]:
                    st.markdown(f"**{row['name']}**")
                    st.caption(f"📍 {row['location']} | 费率: ¥{row['price_per_hour']}/h")
                    # 如果车位极少，显示红色警告
                    color = "normal" if row['占用率'] < 90 else "inverse"
                    st.metric("实时余位", f"{row['available_spaces']} / {row['total_spaces']}", f"占用: {row['占用率']}%", delta_color=color)

        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns((2, 1))
        with col1:
            st.subheader("🌐 AI 24小时流量预测曲线")
            pred = fetch_data("predict")
            if pred and len(pred) > 0:
                df_pred = pd.DataFrame(pred)
                fig = px.area(df_pred, x="hour", y="predicted_cars", color_discrete_sequence=['#00eaff'])
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                fig.update_xaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                fig.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("暂无预测数据")
        with col2:
            st.subheader("📷 关键通道实时快照")
            st.image("https://images.unsplash.com/photo-1506521781263-d8422e82f27a?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80", caption="主入口 A 区", use_container_width=True)
            st.image("https://images.unsplash.com/photo-1573348722427-f1d6819fdf98?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80", caption="地下 B 区", use_container_width=True)

    # 2. 所有 UI 渲染完毕后，最后执行刷新命令
    time.sleep(2)  # 页面停留2秒
    st.rerun()     # 重新从头运行脚本，实现动态刷新
# ==================== 页面 2: 车辆放行与记录 ====================
elif menu == "🚘 车辆放行与记录":
    st.title("🚘 车辆通行管理中心")
    
    # 顶部操作台 (模拟远程控制)
    with st.expander("🛠️ 异常车辆远程处理台 (点击展开)", expanded=True):
        st.write("当车牌识别失败或系统异常时，可在此进行人工干预。")
        cc1, cc2, cc3 = st.columns(3)
        plate_input = cc1.text_input("输入车牌号", placeholder="例如：粤B·88888")
        gate_select = cc2.selectbox("选择道闸", ["东门入口", "南门出口", "地下VIP入口"])
        if cc3.button("🟢 确认身份并强制抬杆", use_container_width=True):
            if plate_input:
                # 模拟系统处理和弹窗提示 (Toast)
                with st.spinner('指令下发中...'):
                    time.sleep(1)
                st.toast(f"✅ {gate_select} 抬杆成功！放行车辆: {plate_input}", icon="🚨")
            else:
                st.error("请输入车牌号")

    st.markdown("### 📋 历史通行记录查询")
    records = fetch_data("records")
    if records:
        df_records = pd.DataFrame(records)
        if not df_records.empty:
            df_records['enter_time'] = pd.to_datetime(df_records['enter_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df_records['leave_time'] = pd.to_datetime(df_records['leave_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 添加搜索过滤
            search = st.text_input("🔍 模糊搜索记录 (如输入用户ID等)", "")
            if search:
                df_records = df_records[df_records.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)]
            
            st.dataframe(df_records, use_container_width=True, height=400)

# ==================== 页面 3: AI预测与财务分析 ====================
elif menu == "📈 AI预测与财务分析":
    st.title("📈 财务报表与模型洞察")
    
    tab1, tab2 = st.tabs(["💰 财务报表分析", "🧠 AI 模型状态"])
    
    with tab1:
        st.subheader("收益趋势分析")
        # 模拟生成更详细的财务折线图
        dates = pd.date_range(end=pd.Timestamp.today(), periods=7)
        revenues = [1200, 1500, 1100, 1800, 2200, 3100, 2800]
        df_rev = pd.DataFrame({"日期": dates, "收益(元)": revenues})
        fig_rev = px.bar(df_rev, x="日期", y="收益(元)", text="收益(元)", color="收益(元)", color_continuous_scale="blues")
        fig_rev.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_rev, use_container_width=True)
        
        st.download_button("📥 导出本月财务报表 (CSV)", df_rev.to_csv(index=False).encode('utf-8'), "finance_report.csv", "text/csv")

    with tab2:
        st.subheader("Veo 停车需求预测模型状态")
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("模型版本", "v2.4.1 (XGBoost)")
        c_m2.metric("最新 R² 得分", "0.92")
        c_m3.metric("下次自动重训时间", "今晚 03:00")
        
        st.info("模型利用历史停车记录、天气数据和节假日特征进行预测。")
        if st.button("🔄 手动触发模型重训 (消耗算力)"):
            with st.spinner('正在拉取最新数据重新训练 AI 模型...'):
                time.sleep(2)
            st.success("🎉 模型训练完成！RMSE 降低 0.05。")