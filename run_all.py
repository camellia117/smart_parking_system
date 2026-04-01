import subprocess
import sys
import time

def main():
    processes = []
    
    print("🚀 正在一键启动所有服务...\n")
    
    try:
        # 1. 启动 FastAPI 后端 (端口 8000)
        print("启动 [FastAPI 后端]...")
        p_backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload", "--port", "8000"]
        )
        processes.append(p_backend)
        time.sleep(1) # 稍微等待一下，错开输出信息

        # 2. 启动 Streamlit 开发者面板 (端口 8501)
        print("启动 [Streamlit 控制台]...")
        p_streamlit = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "dashboard/dashboard.py", "--server.port", "8501"]
        )
        processes.append(p_streamlit)
        time.sleep(1)

        # 3. 启动前端静态服务器 (替代 VS Code Live Server, 端口 5500)
        print("启动 [前端静态页面服务]...")
        p_frontend = subprocess.Popen(
            [sys.executable, "-m", "http.server", "5500"]
        )
        processes.append(p_frontend)
        
        #4. 如果你有运行实时数据生成脚本的需求，可以取消下面这段的注释
        print("启动 [实时数据模拟器]...")
        p_mock = subprocess.Popen(
            [sys.executable, "-m", "mock_data.realtime_simulator"]
        )
        processes.append(p_mock)

        print("\n✅ 所有服务已成功启动！")
        print("👉 后端 API 文档: http://127.0.0.1:8000/docs")
        print("👉 开发者控制台: http://127.0.0.1:8501")
        print("👉 前端登录页面: http://127.0.0.1:5500/data_screen/login.html")
        print("\n🛑 想要停止运行，请在此终端按下 [Ctrl + C]\n")

        # 保持主进程运行，等待子进程
        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n\n🛑 接收到退出信号，正在安全关闭所有服务...")
        for p in processes:
            p.terminate()
        print("👋 所有服务已关闭，再见！")
        sys.exit(0)

if __name__ == "__main__":
    main()