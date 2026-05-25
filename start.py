"""
ImageNious 启动脚本 — 支持修改配置、检查依赖、启动全栈服务

用法:
  python start.py                        # 默认配置启动
  python start.py --port 8888            # 自定义后端端口
  python start.py --no-frontend          # 仅启动后端
  python start.py --config               # 交互式修改配置后启动
  python start.py --kill                 # 关闭所有端口和服务
"""

import os
import sys
import json
import time

# 清除代理环境变量，防止干扰本地服务启动
for _key in list(os.environ.keys()):
    if _key.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ.pop(_key, None)
import socket
import argparse
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
BACKEND_DIR = PROJECT_DIR / "backend"
FRONTEND_DIR = PROJECT_DIR / "frontend"
ENV_FILE = BACKEND_DIR / ".env"
REDIS_EXE = "D:/AAA/tools/redis/redis-server.exe"
REDIS_CLI = "D:/AAA/tools/redis/redis-cli.exe"
NODE_DIR = "C:/Program Files/nodejs"


def kill_port(port: int):
    """强制释放指定端口上所有进程"""
    r = subprocess.run(f"netstat -ano | findstr :{port}", shell=True,
                       capture_output=True, text=True)
    killed = set()
    for line in r.stdout.split('\n'):
        parts = line.strip().split()
        if len(parts) >= 5 and 'LISTENING' in line:
            pid = parts[-1]
            if pid.isdigit() and pid not in killed and pid != "0":
                killed.add(pid)
                subprocess.run(f"taskkill /F /PID {pid}", shell=True,
                              capture_output=True)
    if killed:
        print(f"[OK] 端口{port}已释放 (关闭{len(killed)}个进程)")
    time.sleep(1)


def kill_all():
    """关闭所有相关进程"""
    for port in [9999, 8000, 5173, 3000]:
        kill_port(port)
    subprocess.run("taskkill /F /IM python.exe 2>nul", shell=True)
    subprocess.run("taskkill /F /IM node.exe 2>nul", shell=True)
    print("[OK] 所有服务已关闭")


def is_port_open(host: str, port: int) -> bool:
    """用 netstat 检查端口，绕过系统代理"""
    import subprocess
    try:
        result = subprocess.run(
            f'netstat -ano | findstr ":{port} " | findstr "LISTENING"',
            shell=True, capture_output=True, text=True, timeout=3,
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except:
        return False


def start_redis(port: int = 6379) -> bool:
    if is_port_open("localhost", port):
        print("[OK] Redis 已在运行")
        return True
    if not Path(REDIS_EXE).exists():
        print("[WARN] Redis 未安装")
        return False
    subprocess.Popen([REDIS_EXE, "--port", str(port)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    if is_port_open("localhost", port):
        print("[OK] Redis 已启动")
        return True
    print("[WARN] Redis 启动失败")
    return False


def start_backend(config: dict) -> subprocess.Popen | None:
    port = config["backend_port"]
    kill_port(port)

    # 等待端口完全释放
    for _ in range(5):
        if not is_port_open("localhost", port):
            break
        time.sleep(1)

    env = os.environ.copy()
    env["HF_HOME"] = "D:/AAA/cache/huggingface"
    env["NO_PROXY"] = "localhost,127.0.0.1"  # 绕过系统代理

    # 使用正确的 Python 解释器
    python_exe = os.environ.get("PYTHON_EXE", sys.executable)
    proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", str(port)],
        cwd=str(BACKEND_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    for _ in range(20):
        time.sleep(1)
        if is_port_open("localhost", port):
            print(f"[OK] 后端: http://localhost:{port}")
            print(f"[OK] 文档: http://localhost:{port}/api/docs")
            return proc

    stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    print(f"[ERR] 后端启动失败:\n{stderr[-500:]}")
    return None


def start_frontend(config: dict) -> subprocess.Popen | None:
    port = config["frontend_port"]
    kill_port(port)

    # 等待端口完全释放
    for _ in range(5):
        if not is_port_open("localhost", port):
            break
        time.sleep(1)

    npx = os.path.join(NODE_DIR, "npx.cmd")
    npm = os.path.join(NODE_DIR, "npm.cmd")

    if not (FRONTEND_DIR / "node_modules").exists():
        print("[INFO] 安装前端依赖...")
        subprocess.run([npm, "install"], cwd=str(FRONTEND_DIR))

    # 更新 Vite 代理
    vite_config = FRONTEND_DIR / "vite.config.ts"
    if vite_config.exists():
        content = vite_config.read_text()
        import re
        content = re.sub(r'target:\s*"http://localhost:\d+"',
                        f'target: "http://localhost:{config["backend_port"]}"',
                        content)
        vite_config.write_text(content)

    proc = subprocess.Popen(
        [npx, "vite", "--port", str(port), "--host"],
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for _ in range(10):
        time.sleep(1)
        if is_port_open("localhost", port):
            print(f"[OK] 前端: http://localhost:{port}")
            return proc

    print("[ERR] 前端启动失败")
    return None


def write_env(config: dict):
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = f"""# ImageNious 环境配置
DB_HOST={config['db_host']}
DB_PORT={config['db_port']}
DB_NAME={config['db_name']}
DB_USER={config['db_user']}
DB_PASSWORD={config['db_password']}
DATABASE_URL=mysql+aiomysql://{config['db_user']}:{config['db_password']}@{config['db_host']}:{config['db_port']}/{config['db_name']}

REDIS_HOST={config['redis_host']}
REDIS_PORT={config['redis_port']}

LLM_API_KEY={config['llm_api_key']}
LLM_API_BASE={config['llm_api_base']}
LLM_MODEL={config['llm_model']}

MIMO_API_KEY={config['mimo_api_key']}
MIMO_API_BASE={config['mimo_api_base']}
MIMO_MODEL={config['mimo_model']}

JWT_SECRET_KEY=image-nious-jwt-secret-key-2026
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=480

TEXT_MODEL_PATH=hfl/chinese-roberta-wwm-ext
IMAGE_VIT_MODEL_PATH=openai/clip-vit-large-patch14
IMAGE_CNN_MODEL_PATH=../models/image/cnn_detection.pth

CORS_ORIGINS=http://localhost:{config['frontend_port']},chrome-extension://*
LOG_LEVEL=INFO
"""
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)


DEFAULT_CONFIG = {
    "backend_port": 8001, "frontend_port": 5173,
    "db_host": "localhost", "db_port": 3306, "db_name": "image_nious",
    "db_user": "root", "db_password": "123456",
    "redis_host": "localhost", "redis_port": 6379,
    "llm_api_key": "sk-5fde2f682c194c8992f30fe91542fab9",
    "llm_api_base": "https://api.deepseek.com/v1",
    "llm_model": "deepseek-chat",
    "mimo_api_key": "tp-ckcc4ib4j528eudeqbu6qvqgm8bwbsm9qwp4wd4y9pes1zah",
    "mimo_api_base": "https://token-plan-cn.xiaomimimo.com/anthropic",
    "mimo_model": "mimo-v2.5-pro",
}


def main():
    parser = argparse.ArgumentParser(description="ImageNious 启动脚本")
    parser.add_argument("--port", type=int, help="后端端口")
    parser.add_argument("--kill", action="store_true", help="关闭所有服务")
    parser.add_argument("--no-frontend", action="store_true")
    parser.add_argument("--no-backend", action="store_true")
    parser.add_argument("--config", action="store_true", help="交互式配置")
    args = parser.parse_args()

    if args.kill:
        kill_all()
        return

    config = DEFAULT_CONFIG.copy()
    if args.port:
        config["backend_port"] = args.port
    if args.config:
        for k in ["backend_port", "db_host", "db_name", "db_user", "db_password"]:
            v = input(f"  {k} [{config[k]}]: ").strip()
            if v: config[k] = int(v) if "port" in k else v

    sys.path.insert(0, str(BACKEND_DIR))
    write_env(config)

    print("\n" + "=" * 50)
    print("  ImageNious AIGC 多模态内容鉴伪平台")
    print("=" * 50)

    # 健康检查
    for name, host, port in [("MySQL", config["db_host"], config["db_port"])]:
        status = "OK" if is_port_open(host, port) else "MISSING"
        print(f"  [{status}] {name}")

    procs = []
    start_redis(config["redis_port"])

    if not args.no_backend:
        bp = start_backend(config)
        if bp: procs.append(bp)

    if not args.no_frontend:
        fp = start_frontend(config)
        if fp: procs.append(fp)

    if not procs:
        return

    print(f"\n[OK] 打开 http://localhost:{config['frontend_port']}")
    print("[INFO] Ctrl+C 停止\n")

    try:
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n正在停止...")
        for p in procs:
            p.terminate()
        kill_port(config["backend_port"])
        kill_port(config["frontend_port"])
        print("已停止")


if __name__ == "__main__":
    main()
