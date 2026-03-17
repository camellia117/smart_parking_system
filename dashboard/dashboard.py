import streamlit as st
import pandas as pd
import joblib
import os
import sys

# 【关键设置】将项目根目录添加到搜索路径，解决模块导入 (ModuleNotFoundError) 问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import SystemUser, ParkingRecord

# 配置 Streamlit 页面的标题和宽屏布局
st.set_page_config(page_title="AI-Parking 开发者大本营", page_icon="👨‍💻", layout="wide")

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

# 工具函数：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


# ================= 页面 1：AI 模型分析 =================
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
    st.markdown("最高权限专区：在此分配系统账号，并控制其访问不同业务终端的权限。")
    
    db = get_db()
    
    # 模块 A: 创建新账号表单
    with st.expander("➕ 点击展开：添加系统新员工账号", expanded=True):
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_user = st.text_input("登录用户名 (Username)")
            with col2:
                new_pwd = st.text_input("登录密码 (Password)", type="password")
            with col3:
                # 角色字典映射
                role_map = {
                    "screen": "💻 数据大屏专员 (仅监控大屏)", 
                    "admin": "⚙️ 业务管理员 (后台管理系统)", 
                    "dev": "👨‍💻 高级开发者 (查看算法看板)"
                }
                new_role = st.selectbox("分配系统操作角色", list(role_map.keys()), format_func=lambda x: role_map[x])
                
            submitted = st.form_submit_button("✅ 创建并授权账号")
            
            if submitted:
                if new_user and new_pwd:
                    # 检查用户名是否已经被注册
                    exist = db.query(SystemUser).filter(SystemUser.username == new_user).first()
                    if exist:
                        st.error(f"❌ 注册失败：用户名 '{new_user}' 已存在，请更换！")
                    else:
                        u = SystemUser(username=new_user, password=new_pwd, role=new_role)
                        db.add(u)
                        db.commit()
                        st.success(f"🎉 成功创建系统账号: **{new_user}**，已赋予 **{role_map[new_role]}** 权限！请刷新页面查看下方列表。")
                else:
                    st.warning("⚠️ 请完整填写用户名和密码！")

    st.markdown("---")
    
    # 模块 B: 账号列表一览
    st.subheader("📋 当前系统已注册员工名单")
    users = db.query(SystemUser).all()
    
    if users:
        user_data = []
        for u in users:
            # 翻译角色显示
            role_display = {
                "screen": "🌟 数据大屏专员", 
                "admin": "🛡️ 业务管理员", 
                "dev": "👑 高级开发者"
            }.get(u.role, "未知角色")
            
            user_data.append({
                "内部识别码 (ID)": u.id, 
                "员工登录名": u.username, 
                "系统分配权限": role_display,
                "权限底层代码": u.role
            })
            
        df_users = pd.DataFrame(user_data)
        # 隐藏索引，显示更加美观
        st.dataframe(df_users, hide_index=True, use_container_width=True)
    else:
        st.info("ℹ️ 目前数据库中没有任何账号记录。系统允许临时使用后门超级账号 (root) 进行登录操作。")