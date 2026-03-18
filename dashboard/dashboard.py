import streamlit as st
import pandas as pd
import joblib
import os
import sys
import requests

# 【关键设置】将项目根目录添加到搜索路径，解决模块导入 (ModuleNotFoundError) 问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import SystemUser, ParkingRecord

# 配置 Streamlit 页面的标题和宽屏布局
st.set_page_config(page_title="AI-Parking 开发者大本营", page_icon="👨‍💻", layout="wide")

# 后端 API 基础地址
API_URL = "http://127.0.0.1:8000"

# ================= 【新增】页面鉴权拦截 (防越权访问) =================
# 1. 初始化会话状态中的登录标记
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False

# 2. 检查 URL 参数中是否带有统一登录页传来的授权 Token
if "auth_token" in st.query_params:
    if st.query_params["auth_token"] == "dev_granted":
        st.session_state.is_authenticated = True
        # 验证通过后，立刻清除 URL 里的参数，防止用户复制带有 token 的网址发给别人
        st.query_params.clear()

# 3. 如果验证未通过，展示拦截信息并停止渲染后续页面
if not st.session_state.is_authenticated:
    st.error("⛔ **权限拒绝：您尚未登录或身份已过期！**")
    st.warning("系统检测到您正试图直接越权访问开发者控制台。出于数据安全考虑，请先前往「统一身份认证中心」验证身份。")
    # 注意：这里的链接请改成你平时在浏览器里打开 login.html 的实际地址（比如 VSCode Live Server 的 5500 端口）
    st.markdown("👉 [点击这里返回登录页面](http://127.0.0.1:5500/data_screen/login.html)") 
    st.stop()  # 关键点：st.stop() 会立刻停止执行后面的 Python 代码，保护数据安全

# ================= 侧边栏导航 =================
st.sidebar.title("👨‍💻 开发者核心中枢")
st.sidebar.markdown("---")
menu = st.sidebar.radio("📌 请选择控制台功能", ["🧠 AI 模型深度分析", "🔐 系统账号权限管理"])

# 为了方便测试，在侧边栏加一个模拟身份切换
current_role = st.sidebar.selectbox("🎭 当前操作身份 (模拟)", ["dev", "root", "admin"], help="只有 root 或 dev 可以进行修改和删除操作")

# 工具函数：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

# ================= 与 FastAPI 交互的辅助函数 =================
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
        st.error(f"无法连接到后端 API，请确认 FastAPI (8000端口) 已启动: {e}")
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


# ================= 页面 1：AI 模型分析 (保持原有不动) =================
if menu == "🧠 AI 模型深度分析":
    st.title("🧠 AI 预测模型状态大盘")
    st.markdown("这里是数据科学家和算法工程师的专属监控台，用于评估**随机森林多特征时序预测模型**的健康度。")

    col1, col2 = st.columns([1, 1])
    
    # 模块 1：加载并展示模型信息
    with col1:
        st.subheader("📦 模型文件加载状态")
        model_path = "ai_prediction/model.pkl"
        
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            st.success(f"✅ 成功加载本地模型: `{model_path}`")
            st.info(f"**核心算法**: {type(model).__name__}")
            
            # 展示随机森林参数
            if hasattr(model, 'n_estimators'):
                st.write(f"- 决策树数量 (n_estimators): **{model.n_estimators}**")
            
            # 绘制特征重要性柱状图
            if hasattr(model, 'feature_importances_'):
                st.subheader("📊 模型特征重要性 (Feature Importance)")
                # 对应我们在 train_model.py 里的四个特征
                features = ["时间 (Hour)", "星期 (Day of Week)", "是否周末 (Weekend)", "天气 (Weather)"]
                importances = model.feature_importances_
                
                if len(importances) == len(features):
                    feat_df = pd.DataFrame({"特征": features, "重要度权重": importances})
                    feat_df = feat_df.sort_values(by="重要度权重", ascending=False)
                    # 使用 Streamlit 原生图表
                    st.bar_chart(feat_df.set_index("特征"))
                else:
                    st.write(f"检测到特征数量 ({len(importances)}) 与预设 ({len(features)}) 不符，请确认是否更新了训练脚本。")
        else:
            st.error("❌ 未找到模型文件，请先在终端运行 `python -m ai_prediction.train_model`")

    # 模块 2：数据库原始训练数据查阅
    with col2:
        st.subheader("📈 训练集数据提取情况")
        db = get_db()
        # 提取最新 50 条停车记录
        records = db.query(ParkingRecord).order_by(ParkingRecord.id.desc()).limit(50).all()
        
        if records:
            df = pd.DataFrame([{
                "记录ID": r.id, 
                "入场时间": r.enter_time, 
                "离开时间": r.leave_time,
                "产生费用": r.fee,
                # 兼容防错设计，防止旧数据库没有这些字段
                "是否周末": getattr(r, 'is_weekend', "未知"),
                "天气状态": getattr(r, 'weather_type', "未知")
            } for r in records])
            
            st.dataframe(df, use_container_width=True)
            st.caption("提示: 仅展示最新 50 条原始特征数据。真实训练集将包含全库数据。")
        else:
            st.warning("⚠️ 数据库中暂无停车记录，AI 目前处于缺乏训练数据的状态。")


# ================= 页面 2：系统账号权限管理 =================
elif menu == "🔐 系统账号权限管理":
    st.title("🔐 全局 RBAC 权限与人员管理")
    st.markdown("在此分配系统账号，并控制其访问不同业务终端的权限。支持多维度查询与信息修改。")
    
    # --- 1. 顶部查询区 ---
    search_query = st.text_input("🔍 账号检索 (支持通过「登录名」或「手机号码」进行模糊匹配搜索)", "")
    
    # 获取后端用户数据
    users = fetch_users(search_query)
    
    # --- 2. 账号展示区 ---
    st.markdown("### 📋 系统人员登记表")
    if users:
        df = pd.DataFrame(users)
        # 兼容旧数据库可能没有 phone 字段的情况
        if 'phone' not in df.columns:
            df['phone'] = ""
            
        # 选择要展示的列，并进行重命名和排序
        display_df = df[['id', 'username', 'role', 'phone', 'password']]
        display_df.columns = ['账户 ID', '登录名', '角色权限', '绑定手机号', '登录密码']
        
        # 隐藏最左侧自带的丑陋序号索引，让表格更像管理后台
        st.dataframe(display_df, hide_index=True, use_container_width=True)
        
        # --- 3. 高级操作区 (只有 root 和 dev 才能看到并使用) ---
        if current_role in ["root", "dev"]:
            st.markdown("---")
            st.subheader("🛠️ 高级安全操作区 (超级管理员权限)")
            
            op_col1, op_col2 = st.columns(2)
            
            # 编辑修改面板
            with op_col1:
                st.markdown("#### ✏️ 编辑与重置")
                edit_id = st.selectbox("请选择要修改的【账户 ID】", df['id'].tolist(), key="edit_select")
                
                if edit_id:
                    # 提取选中用户的当前信息填入表单
                    target_user = df[df['id'] == edit_id].iloc[0]
                    with st.form("edit_user_form"):
                        new_username = st.text_input("登录名", value=target_user['username'])
                        new_password = st.text_input("登录密码", value=target_user['password'])
                        
                        # 处理有些旧账号手机号是 null 的情况
                        phone_val = target_user['phone']
                        new_phone = st.text_input("绑定手机号", value=phone_val if pd.notna(phone_val) else "")
                        
                        if st.form_submit_button("💾 保存信息修改"):
                            success, msg = update_user(edit_id, new_username, new_password, new_phone)
                            if success:
                                st.success("✅ 账号信息已成功更新！")
                                st.rerun()  # 立即刷新页面更新表格
                            else:
                                st.error(f"❌ 更新失败: {msg.get('detail', msg)}")
            
            # 永久删除面板
            with op_col2:
                st.markdown("#### ⚠️ 危险操作")
                del_id = st.selectbox("请选择要注销的【账户 ID】", df['id'].tolist(), key="del_select")
                st.warning("注销后无法恢复，请谨慎操作！")
                
                if st.button("🗑️ 彻底注销该账号", type="primary"):
                    if del_id:
                        success, msg = delete_user(del_id)
                        if success:
                            st.success("✅ 账号已被永久删除！")
                            st.rerun()
                        else:
                            st.error(f"❌ 删除失败: {msg.get('detail', msg)}")
        else:
            st.info("💡 提示: 您当前登录的身份为普通管理员，仅有查看权限。如需修改或删除账号，请使用 root 或 dev 身份登录。")
    else:
        st.warning("📭 未检索到符合条件的账号记录。")

    # --- 4. 添加新账号区 ---
    st.markdown("---")
    st.subheader("➕ 添加系统新员工")
    with st.form("add_user_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_username = st.text_input("登录用户名 (Username)")
            new_password = st.text_input("初始登录密码 (Password)")
        with col2:
            # 角色字典映射
            role_map = {
                "screen": "💻 数据大屏专员 (仅监控大屏)", 
                "admin": "⚙️ 业务管理员 (后台管理系统)", 
                "dev": "👨‍💻 高级开发者 (查看算法看板)"
            }
            new_role = st.selectbox("分配系统操作角色", list(role_map.keys()), format_func=lambda x: role_map[x])
            new_phone = st.text_input("绑定手机号 (用于找回密码必填)")
        with col3:
            st.markdown("<br><br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("✅ 创建并授权账号")
            
        if submitted:
            if new_username and new_password and new_phone:
                success, response = add_user(new_username, new_password, new_role, new_phone)
                if success:
                    st.success(f"🎉 成功创建 {new_role} 账号: **{new_username}**！")
                    st.rerun()
                else:
                    st.error(f"❌ 创建失败: {response.get('detail', '未知错误')}")
            else:
                st.warning("⚠️ 请务必完整填写用户名、密码和手机号！")