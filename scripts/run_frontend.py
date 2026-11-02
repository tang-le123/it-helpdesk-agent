"""PyCharm 运行项：启动 Adaptive-rag 的 Vite 前端。"""
import subprocess
from pathlib import Path

frontend = Path(__file__).resolve().parents[1] / "frontend"
cmd = ["cmd", "/c", "npm", "run", "dev"]
print(f"Starting frontend: {' '.join(cmd)}")
print(f"Working directory: {frontend}")
raise SystemExit(subprocess.call(cmd, cwd=frontend))
