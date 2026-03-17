import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
from streamlit_autorefresh import st_autorefresh

# ==================== 0. 页面基础与状态配置 ====================
st.set_page_config(page_title="智慧停车管控中枢 V8", layout="wide", page_icon="🌌")
st_autorefresh(interval=3000, key="dashboard_autorefresh")

if 'dashboard_memory' not in st.session_state:
    st.session_state.dashboard_memory = {}

# ==================== 1. 大师级全局 CSS ====================
# 这里将第一行顶格，避免触发 Markdown 的代码块机制
st.markdown("""
<style>
.main {background-color: #050914;}
.stApp {background-image: radial-gradient(circle at 50% 0%, #111a2f 0%, #050914 80%);}
h1, h2, h3 {color: #ffffff !important; font-family: 'Arial', sans-serif; text-shadow: 0 0 10px rgba(255,255,255,0.2);}
.css-1d391kg {background-color: #0a0f1d !important; border-right: 1px solid #1f3a5f;}

.custom-card {
    box-sizing: border-box;
    background: linear-gradient(145deg, rgba(20, 30, 50, 0.9), rgba(10, 15, 30, 0.8));
    border: 1px solid rgba(0, 234, 255, 0.15); 
    padding: 20px 15px; 
    border-radius: 16px; 
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
    margin-bottom: 1rem;
    transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.3s ease, border-color 0.3s ease;
    overflow: hidden; 
}

/* 绝对固定高度，杜绝跳动 */
.top-card { height: 160px; }
.lot-card { height: 230px; }

.custom-card:hover { 
    transform: scale(1.05); 
    border-color: #00eaff; 
    box-shadow: 0 10px 30px rgba(0,234,255,0.25); 
    z-index: 10;
}

.value-box { height: 50px; width: 100%; display: flex; align-items: center; overflow: hidden; margin: 5px 0; }
.lot-value-box { height: 40px; } 

.c-label { font-size: 1.05rem; color: #8cb6f5; font-weight: bold;}
.c-value { font-size: 2.6rem; font-weight: 900; color: #ffffff; text-shadow: 0 0 15px rgba(0,234,255,0.3); line-height: 1; display: inline-block;}
.lot-val { font-size: 2.1rem; }

.c-delta { font-size: 0.9rem; color: #ffeb7b; font-weight: bold;}
.c-delta.down { color: #ff4683; }

.lot-title { font-size: 1.15rem; font-weight: bold; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 3px;}
.lot-loc { font-size: 0.85rem; color: #8cb6f5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}

.progress-bg { background: rgba(255,255,255,0.1); border-radius: 6px; width: 100%; height: 8px; margin: 12px 0; overflow: hidden;}
.progress-bar { height: 100%; border-radius: 6px; box-shadow: 0 0 8px currentColor; transition: width 0.5s ease; }
</style>
""", unsafe_allow_html=True)

# ==================== 2. Python 智能渲染引擎 ====================
def render_animated_metric(label, value, delta, key_id, is_down=False):
    old_val = st.session_state.dashboard_memory.get(key_id)
    changed = (old_val is not None) and (str(old_val) != str(value))
    st.session_state.dashboard_memory[key_id] = str(value)
    
    anim_css = ""
    style_block = ""
    if changed:
        run_id = int(time.time() * 1000)
        anim_css = f"animation: slotRoll_{run_id} 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) both;"
        # 这里的 CSS 也全部顶格写！
        style_block = f"""
<style>
@keyframes slotRoll_{run_id} {{
0% {{ transform: translateY(-30px); opacity: 0; color: #00eaff; }}
80% {{ transform: translateY(2px); }}
100% {{ transform: translateY(0); opacity: 1; color: #ffffff; }}
}}
</style>
"""
        
    delta_class = "c-delta down" if is_down else "c-delta"
    
    # 【核心修复】：所有的 HTML 标签全部顶格，坚决不留哪怕一个空格缩进！
    html = f"""{style_block}
<div class="custom-card top-card">
<div class="c-label">{label}</div>
<div class="value-box">
<div class="c-value" style="{anim_css}">{value}</div>
</div>
<div class="{delta_class}">{delta}</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)

def render_lot_card(row, key_id):
    name = row.get('name', '未知停车场')
    loc = row.get('location', '未知位置')
    price = row.get('price_per_hour', 0)
    total = int(row.get('total_spaces', 0))
    avail = int(row.get('available_spaces', 0))
    
    value_str = f"{avail} / {total}"
    
    old_val = st.session_state.dashboard_memory.get(key_id)
    changed = (old_val is not None) and (str(old_val) != str(value_str))
    st.session_state.dashboard_memory[key_id] = str(value_str)
    
    anim_css = ""
    style_block = ""
    if changed:
        run_id = int(time.time() * 1000)
        anim_css = f"animation: slotRoll_{run_id} 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) both;"
        style_block = f"""
<style>
@keyframes slotRoll_{run_id} {{
0% {{ transform: translateY(-30px); opacity: 0; color: #00eaff; }}
80% {{ transform: translateY(2px); }}
100% {{ transform: translateY(0); opacity: 1; color: #ffffff; }}
}}
</style>
"""

    ratio = 0 if total == 0 else avail / total
    ratio_pct = int((1 - ratio) * 100) 
    bar_color = "#ff4683" if ratio_pct >= 90 else "#00eaff"

    # 【核心修复】：所有的 HTML 标签全部顶格，坚决不留哪怕一个空格缩进！
    html = f"""{style_block}
<div class="custom-card lot-card">
<div class="lot-title">{name}</div>
<div class="lot-loc">📍 {loc} | ¥{price}/h</div>
<div class="progress-bg">
<div class="progress-bar" style="width:{ratio_pct}%; background:{bar_color};"></div>
</div>
<div class="c-label">实时余位</div>
<div class="value-box lot-value-box">
<div class="c-value lot-val" style="{anim_css}">{value_str}</div>
</div>
<div class="c-delta {'down' if ratio_pct>=90 else ''}">占用: {ratio_pct}%</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)

# ==================== 3. 导航与接口 ====================

# 1. 注入 CSS 彻底隐藏 Streamlit 原生的侧边栏和左上角的展开按钮
st.markdown("""
<style>
[data-testid="collapsedControl"] {display: none !important;} 
section[data-testid="stSidebar"] {display: none !important;}
/* 减少顶部留白，让嵌入 HTML 时更自然 */
.block-container {padding-top: 1rem !important;} 
</style>
""", unsafe_allow_html=True)

# 2. 改用 URL Query 参数来控制当前页面
# 例如：访问 http://localhost:8502/?menu=1 就会显示大盘
menu_param = st.query_params.get("menu", "1")

if menu_param == "1":
    menu = "📊 实时监控大盘"
elif menu_param == "2":
    menu = "🚘 车辆放行与记录"
elif menu_param == "3":
    menu = "📈 AI预测与财务分析"
else:
    menu = "📊 实时监控大盘"

@st.cache_data(ttl=1)  
def fetch_data(endpoint):
    try:
        return requests.get(f"http://127.0.0.1:8000/{endpoint}").json()
    except:
        return None

# ==================== 页面 1: 实时监控大盘 ====================
if menu == "📊 实时监控大盘":
    st.title("📊 城市级实时监控大盘")
    
    stats = fetch_data("statistics")
    if stats:
        c1, c2, c3, c4 = st.columns(4)
        with c1: render_animated_metric("🅿️ 累计服务车次", f"{stats.get('records', 0)}", "⬆️ +12 辆 (较昨日)", "top_records")
        with c2: render_animated_metric("💰 实时累计流水", f"¥ {stats.get('total_revenue', 0):.2f}", "⬆️ +5.4% 营收", "top_rev")
        with c3: render_animated_metric("⏱️ 平均驻留时长", f"{stats.get('avg_parking_time', 0):.1f}", "⬇️ -0.2 小时", "top_time", is_down=True)
        with c4: render_animated_metric("🚨 违停警告", "3", "🛡️ 保安已就位", "top_warn", is_down=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 中部：停车场阵列
        st.subheader("🏙️ 城市路网停车场实时阵列")
        lots_data = fetch_data("lots")
        
        if lots_data is not None:
            if len(lots_data) > 0:
                lots_df = pd.DataFrame(lots_data)
                lot_cols = st.columns(len(lots_df))
                for idx, row in lots_df.iterrows():
                    with lot_cols[idx]:
                        render_lot_card(row, f"lot_{row.get('id', idx)}")
            else:
                st.info("ℹ️ 数据库中暂无停车场数据。")
        else:
            st.error("❌ 无法连接到后端获取停车场数据。")

        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns((2, 1))
        with col1:
            st.subheader("🌐 AI 24小时流量预测曲线")
            pred = fetch_data("predict")
            if pred and len(pred) > 0:
                df_pred = pd.DataFrame(pred)
                fig = px.area(df_pred, x="hour", y="predicted_cars", color_discrete_sequence=['#00eaff'])
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white", margin=dict(l=0, r=0, t=30, b=0))
                fig.update_xaxes(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
                fig.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("暂无预测数据")
        with col2:
            st.subheader("📷 关键通道实时快照")
            st.image("https://images.unsplash.com/photo-1506521781263-d8422e82f27a?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80", caption="主入口 A 区", use_container_width=True)
            st.image("https://images.unsplash.com/photo-1573348722427-f1d6819fdf98?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80", caption="地下 B 区", use_container_width=True)
    else:
        st.warning("⏳ 正在等待核心系统数据同步中...")

# ==================== 页面 2 & 3 保持不变 ====================
elif menu == "🚘 车辆放行与记录":
    st.title("🚘 车辆通行管理中心")
    with st.expander("🛠️ 异常车辆远程处理台 (点击展开)", expanded=True):
        cc1, cc2, cc3 = st.columns(3)
        plate_input = cc1.text_input("输入车牌号", placeholder="例如：粤B·88888")
        gate_select = cc2.selectbox("选择道闸", ["东门入口", "南门出口", "地下VIP入口"])
        if cc3.button("🟢 确认身份并强制抬杆", use_container_width=True):
            if plate_input:
                with st.spinner('指令下发中...'): time.sleep(1)
                st.toast(f"✅ {gate_select} 抬杆成功！放行车辆: {plate_input}", icon="🚨")
                st.cache_data.clear() 
            else:
                st.error("请输入车牌号")

    st.markdown("### 📋 历史通行记录查询")
    records = fetch_data("records")
    if records:
        df_records = pd.DataFrame(records)
        if not df_records.empty:
            df_records['enter_time'] = pd.to_datetime(df_records['enter_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df_records['leave_time'] = pd.to_datetime(df_records['leave_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            search = st.text_input("🔍 模糊搜索记录", "")
            if search:
                df_records = df_records[df_records.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)]
            st.dataframe(df_records, use_container_width=True, height=400)

elif menu == "📈 AI预测与财务分析":
    st.title("📈 财务报表与模型洞察")
    tab1, tab2 = st.tabs(["💰 财务报表分析", "🧠 AI 模型状态"])
    with tab1:
        st.subheader("收益趋势分析")
        dates = pd.date_range(end=pd.Timestamp.today(), periods=7)
        revenues = [1200, 1500, 1100, 1800, 2200, 3100, 2800]
        df_rev = pd.DataFrame({"日期": dates, "收益(元)": revenues})
        fig_rev = px.bar(df_rev, x="日期", y="收益(元)", text="收益(元)", color="收益(元)", color_continuous_scale="blues")
        fig_rev.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_rev, use_container_width=True)
    with tab2:
        st.subheader("Veo 停车需求预测模型状态")
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1: render_animated_metric("模型版本", "v2.4.1", "XGBoost 引擎", "ai_ver")
        with c_m2: render_animated_metric("最新 R² 得分", "0.92", "拟合度极佳", "ai_score")
        with c_m3: render_animated_metric("下次重训时间", "03:00", "今晚自动执行", "ai_time")