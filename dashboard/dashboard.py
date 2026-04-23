import streamlit as st
import pandas as pd
import joblib
import os
import sys
import requests

# 将项目根目录添加到搜索路径，解决模块导入问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import SystemUser, ParkingRecord

# ================= 页面基础配置 =================
st.set_page_config(page_title="AI-Parking | 开发者中枢", layout="wide", initial_sidebar_state="expanded")

# ================= 全局极简高级 CSS 注入 =================
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            color: #1d1d1f;
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        h1, h2, h3, h4 {
            color: #1d1d1f;
            font-weight: 600 !important;
            letter-spacing: -0.5px !important;
        }

        .stButton>button {
            background-color: #1d1d1f !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            border: none !important;
            padding: 0.5rem 1.2rem !important;
            font-weight: 500 !important;
            letter-spacing: 0.2px !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
        }
        .stButton>button:hover {
            background-color: #333333 !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
        }

        button[kind="primary"] {
            background-color: #e3342f !important;
        }
        button[kind="primary"]:hover {
            background-color: #cc2a25 !important;
        }

        .apple-link {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            background: #fbfbfd;
            color: #1d1d1f !important;
            font-weight: 500;
            text-decoration: none;
            border-radius: 8px;
            margin-bottom: 8px;
            transition: all 0.2s ease;
            font-size: 13px;
            border: 1px solid rgba(0, 0, 0, 0.05);
        }
        .apple-link:hover {
            background: #f5f5f7;
            text-decoration: none;
        }
        .apple-link i {
            margin-right: 12px;
            color: #86868b;
            font-size: 14px;
            width: 16px;
            text-align: center;
        }

        hr {
            border: none;
            height: 1px;
            background-color: #d2d2d7;
            margin: 2rem 0;
        }
        
        .stTextInput>div>div>input {
            border-radius: 8px;
            border: 1px solid #d2d2d7;
            transition: border-color 0.2s;
        }
        .stTextInput>div>div>input:focus {
            border-color: #0071e3 !important;
            box-shadow: 0 0 0 1px #0071e3 !important;
        }
    </style>
""", unsafe_allow_html=True)

# 后端 API 基础地址
API_URL = "http://127.0.0.1:8000"

# ================= 页面鉴权拦截 (防越权访问) =================
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False

if "auth_token" in st.query_params:
    if st.query_params["auth_token"] == "dev_granted":
        st.session_state.is_authenticated = True
        st.query_params.clear()

if not st.session_state.is_authenticated:
    st.markdown("### <i class='fa-solid fa-lock' style='color:#86868b; margin-right:8px;'></i> 访问受限", unsafe_allow_html=True)
    st.markdown("<p style='color: #86868b; font-size: 14px;'>系统检测到您正试图越权访问开发者控制台。出于数据安全考虑，请先通过统一身份认证中心验证您的身份。</p>", unsafe_allow_html=True)
    st.markdown("""
        <a href="http://127.0.0.1:5500/data_screen/login.html" style="display: inline-block; margin-top: 16px; padding: 10px 20px; background: #1d1d1f; color: #fff; text-decoration: none; border-radius: 8px; font-size: 13px; font-weight: 500;">
            前往统一登录
        </a>
    """, unsafe_allow_html=True)
    st.stop()  

# ================= 工具函数 =================
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

def fetch_users(search_query=""):
    try:
        url = f"{API_URL}/system_users/"
        if search_query:
            url += f"?search={search_query}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"无法连接到核心 API (8000端口)。错误详情: {e}")
        return []

def add_user(username, password, role, phone):
    try:
        data = {"username": username, "password": password, "role": role, "phone": phone}
        response = requests.post(f"{API_URL}/system_users/", json=data)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"detail": str(e)}

def update_user(user_id, username, password, phone):
    try:
        data = {"id": user_id, "username": username, "password": password, "phone": phone}
        response = requests.put(f"{API_URL}/system_users/", json=data)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"detail": str(e)}

def delete_user(user_id):
    try:
        response = requests.delete(f"{API_URL}/system_users/{user_id}")
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"detail": str(e)}


# ================= 侧边栏导航 =================
st.sidebar.markdown("<h3 style='font-size: 16px;'><i class='fa-solid fa-layer-group' style='color:#86868b; margin-right:8px;'></i> 核心中枢</h3>", unsafe_allow_html=True)
st.sidebar.markdown("<hr style='margin: 16px 0; background-color: rgba(0,0,0,0.05);'>", unsafe_allow_html=True)

menu = st.sidebar.radio("模块导航", ["AI 模型深度分析", "系统账号与权限"], label_visibility="collapsed")

st.sidebar.markdown("<h4 style='color: #86868b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; margin: 32px 0 12px 4px;'>快速通道</h4>", unsafe_allow_html=True)

st.sidebar.markdown("""
    <div style="display: flex; flex-direction: column;">
        <a href="http://127.0.0.1:5500/data_screen/admin.html" target="_blank" class="apple-link">
            <i class="fa-solid fa-server"></i> 业务管理后台
        </a>
        <a href="http://127.0.0.1:5500/data_screen/screen.html" target="_blank" class="apple-link">
            <i class="fa-solid fa-desktop"></i> 调度监控大屏
        </a>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<hr style='margin: 24px 0 16px 0; background-color: rgba(0,0,0,0.05);'>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='color: #86868b; font-size: 11px; margin-bottom: 8px; padding-left: 4px;'>环境沙箱身份模拟</p>", unsafe_allow_html=True)
current_role = st.sidebar.selectbox("身份模拟", ["dev", "root", "admin"], label_visibility="collapsed")


# ================= 页面 1：AI 模型分析 =================
if menu == "AI 模型深度分析":
    st.markdown("## <i class='fa-solid fa-brain' style='color:#86868b; margin-right:8px; font-size: 24px;'></i> AI 预测模型状态大盘", unsafe_allow_html=True)
    st.markdown("<p style='color: #86868b; font-size: 14px; margin-bottom: 32px;'>专属算法监控台，用于评估随机森林多特征时序预测模型的健康度与特征表现。</p>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("<h3 style='font-size: 16px; margin-bottom: 16px;'><i class='fa-solid fa-box-archive' style='color:#86868b; margin-right:8px;'></i> 模型加载状态</h3>", unsafe_allow_html=True)
        model_path = "ai_prediction/model.pkl"
        
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            st.success(f"本地模型挂载成功: {model_path}")
            st.markdown(f"<p style='font-size: 13px; color: #1d1d1f;'><strong>核心算法架构</strong>: {type(model).__name__}</p>", unsafe_allow_html=True)
            
            if hasattr(model, 'n_estimators'):
                st.markdown(f"<p style='font-size: 13px; color: #1d1d1f;'>决策树节点规模: <strong>{model.n_estimators}</strong></p>", unsafe_allow_html=True)
            
            if hasattr(model, 'feature_importances_'):
                st.markdown("<h3 style='font-size: 14px; margin: 32px 0 16px 0; color: #86868b;'>特征重要性分布 (Feature Importance)</h3>", unsafe_allow_html=True)
                features = ["时间 (Hour)", "星期 (Day of Week)", "是否周末 (Weekend)", "天气 (Weather)"]
                importances = model.feature_importances_
                
                if len(importances) == len(features):
                    feat_df = pd.DataFrame({"特征": features, "权重系数": importances})
                    feat_df = feat_df.sort_values(by="权重系数", ascending=False)
                    st.bar_chart(feat_df.set_index("特征"))
                else:
                    st.info("特征向量维度发生变更，图表已挂起。")
        else:
            st.error("未找到本地模型切片，请确认训练管道是否正常运行。")

    with col2:
        st.markdown("<h3 style='font-size: 16px; margin-bottom: 16px;'><i class='fa-solid fa-database' style='color:#86868b; margin-right:8px;'></i> 训练集抽样数据</h3>", unsafe_allow_html=True)
        db = get_db()
        records = db.query(ParkingRecord).order_by(ParkingRecord.id.desc()).limit(50).all()
        
        if records:
            df = pd.DataFrame([{
                "ID": r.id, 
                "入场时间": r.enter_time.strftime("%Y-%m-%d %H:%M") if r.enter_time else "-", 
                "离场时间": r.leave_time.strftime("%Y-%m-%d %H:%M") if r.leave_time else "-",
                "费率": f"¥ {r.fee}" if r.fee else "-",
                "周末标识": getattr(r, 'is_weekend', "缺失"),
                "环境特征": getattr(r, 'weather_type', "缺失")
            } for r in records])
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown("<p style='font-size: 12px; color: #86868b; margin-top: 8px;'>数据快照：当前视图仅展示最新的 50 条特征源数据。</p>", unsafe_allow_html=True)
        else:
            st.warning("底层数据仓库暂时为空，模型特征提取通道已休眠。")

# ================= 页面 2：系统账号权限管理 =================
elif menu == "系统账号与权限":
    st.markdown("## <i class='fa-solid fa-shield-halved' style='color:#86868b; margin-right:8px; font-size: 24px;'></i> RBAC 权限与人员调度", unsafe_allow_html=True)
    st.markdown("<p style='color: #86868b; font-size: 14px; margin-bottom: 24px;'>分配和管理系统级操作人员的访问权限，确保业务模块的访问安全与数据隔离。</p>", unsafe_allow_html=True)
    
    search_query = st.text_input("全局检索 (支持登录名 / 手机号码进行模糊匹配)", "")
    users = fetch_users(search_query)
    
    st.markdown("<h3 style='font-size: 16px; margin: 32px 0 16px 0;'><i class='fa-solid fa-list' style='color:#86868b; margin-right:8px;'></i> 访问授权清单</h3>", unsafe_allow_html=True)
    if users:
        df = pd.DataFrame(users)
        if 'phone' not in df.columns:
            df['phone'] = ""
            
        display_df = df[['id', 'username', 'role', 'phone', 'password']]
        display_df.columns = ['账户凭证 ID', '系统登录名', '访问角色', '安全绑定手机', '加密密钥']
        st.dataframe(display_df, hide_index=True, use_container_width=True)
        
        if current_role in ["root", "dev"]:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("<h3 style='font-size: 16px; margin-bottom: 24px;'><i class='fa-solid fa-sliders' style='color:#86868b; margin-right:8px;'></i> 高级配置控制台</h3>", unsafe_allow_html=True)
            
            op_col1, op_col2 = st.columns(2, gap="large")
            with op_col1:
                st.markdown("<h4 style='font-size: 14px; margin-bottom: 16px;'>信息覆写</h4>", unsafe_allow_html=True)
                edit_id = st.selectbox("指定目标凭证 ID", df['id'].tolist(), key="edit_select")
                
                if edit_id:
                    # 【🐛修复此处】这里已经修改为使用 df 的原生英文字段，防止 KeyError
                    target_user = df[df['id'] == edit_id].iloc[0]
                    with st.form("edit_user_form"):
                        new_username = st.text_input("重设登录名", value=target_user['username'])
                        new_password = st.text_input("重设密钥", value=target_user['password'])
                        phone_val = target_user['phone']
                        new_phone = st.text_input("更新安全手机", value=phone_val if pd.notna(phone_val) else "")
                        
                        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
                        if st.form_submit_button("保存配置变更"):
                            success, msg = update_user(edit_id, new_username, new_password, new_phone)
                            if success:
                                st.success("系统提示：凭证配置已成功同步。")
                                st.rerun()  
                            else:
                                st.error(f"同步异常: {msg.get('detail', msg)}")
            
            with op_col2:
                st.markdown("<h4 style='font-size: 14px; margin-bottom: 16px; color: #e3342f;'>凭证吊销</h4>", unsafe_allow_html=True)
                del_id = st.selectbox("选择需吊销的凭证 ID", df['id'].tolist(), key="del_select")
                st.markdown("<p style='font-size: 12px; color: #86868b; margin-bottom: 16px;'>注意：凭证注销属于不可逆的破坏性操作，对应的模块访问权将被立刻阻断。</p>", unsafe_allow_html=True)
                
                if st.button("强制吊销", type="primary"):
                    if del_id:
                        success, msg = delete_user(del_id)
                        if success:
                            st.success("系统提示：指定凭证已被永久移除。")
                            st.rerun()
                        else:
                            st.error(f"阻断异常: {msg.get('detail', msg)}")
        else:
            st.info("受限视图：当前所处的身份组别仅拥有只读权限，配置修改入口已锁定。")
    else:
        st.markdown("<p style='color: #86868b; font-size: 14px;'>暂无符合查询条件的凭证记录。</p>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size: 16px; margin-bottom: 24px;'><i class='fa-solid fa-user-plus' style='color:#86868b; margin-right:8px;'></i> 签发新凭证</h3>", unsafe_allow_html=True)
    with st.form("add_user_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3, gap="medium")
        with col1:
            new_username = st.text_input("指定登录名")
            new_password = st.text_input("下发初始密钥")
        with col2:
            role_map = {
                "screen": "数据大屏监控组", 
                "admin": "后台业务管理组", 
                "dev": "算法与架构组 (系统最高)"
            }
            new_role = st.selectbox("分配职能角色", list(role_map.keys()), format_func=lambda x: role_map[x])
            new_phone = st.text_input("安全手机号 (必填项)")
        with col3:
            st.markdown("<div style='margin-top: 31px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("签发并入库")
            
        if submitted:
            if new_username and new_password and new_phone:
                success, response = add_user(new_username, new_password, new_role, new_phone)
                if success:
                    st.success(f"凭证签发成功，身份标识: {new_username}")
                    st.rerun()
                else:
                    st.error(f"签发受阻: {response.get('detail', '服务端抛出未知异常')}")
            else:
                st.warning("信息输入不完整，请补充全部字段后重试。")