import subprocess
import sys
import time
import socket
import os

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def main():
    # 【关键修复 1】：屏蔽系统全局代理对本地环回地址的拦截，解决 Streamlit 白屏和本地组件失效
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
    
    print("🔍 正在进行运行环境自检...")
    ports_to_check = {"FastAPI后端": 8000, "Streamlit大屏": 8501, "前端静态服务": 5500}
    conflict = False
    
    for name, port in ports_to_check.items():
        if is_port_in_use(port):
            print(f"❌ 严重错误: 端口 {port} ({name}) 已被旧进程占用！")
            conflict = True
            
    if conflict:
        print("\n⚠️ 发现‘僵尸进程’！继续运行会导致新代码无法生效。")
        print("👉 解决方案: 请在终端面板删除所有终端，然后重新运行本脚本。")
        sys.exit(1)

    print("✅ 端口检查通过，准备启动所有服务...\n")

    no_cache_server_code = """
import http.server
import socketserver

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

if __name__ == '__main__':
    socketserver.TCPServer(("", 5500), NoCacheHandler).serve_forever()
"""
    with open("dev_server.py", "w", encoding="utf-8") as f:
        f.write(no_cache_server_code.strip())

    processes = []
    try:
        print("🚀 启动 [FastAPI 后端] (端口 8000)...")
        p_backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--reload", "--port", "8000"])
        processes.append(p_backend)
        time.sleep(1.5)

        print("🚀 启动 [Streamlit 控制台] (端口 8501)...")
        # 【关键修复 2】：关闭 Streamlit 的 CORS 和 XSRF，防止代理环境下的 WebSocket 断连
        p_streamlit = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "dashboard/dashboard.py", 
            "--server.port", "8501",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false"
        ])
        processes.append(p_streamlit)
        time.sleep(1.5)

        print("🚀 启动 [前端无缓存服务] (端口 5500)...")
        p_frontend = subprocess.Popen([sys.executable, "dev_server.py"])
        processes.append(p_frontend)

        print("\n" + "="*55)
        print("✨ 所有服务已成功启动！请按住 Ctrl 键点击以下链接访问：")
        print("💻 1. 前端业务系统: http://127.0.0.1:5500/data_screen/login.html")
        print("📊 2. 开发者控制台: http://127.0.0.1:8501")
        print("🔌 3. 后端 API 文档: http://127.0.0.1:8000/docs")
        print("="*55)
        print("🛑 想要停止运行，请在此终端按下 [Ctrl + C]\n")

        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n\n🛑 接收到退出信号，正在安全清理所有进程...")
        for p in processes:
            p.terminate()
        if os.path.exists("dev_server.py"):
            os.remove("dev_server.py")
        print("👋 所有服务已彻底关闭，干得漂亮！")
        sys.exit(0)

if __name__ == "__main__":
    main()