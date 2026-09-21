import sys
import os

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import subprocess
from pathlib import Path

# Tự động chuyển sang môi trường ảo venv nếu chạy bằng python ngoài
BASE_DIR = Path(__file__).resolve().parent
if sys.platform == "win32":
    VENV_PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"
else:
    VENV_PYTHON = BASE_DIR / "venv" / "bin" / "python3"

if VENV_PYTHON.exists() and sys.executable.lower() != str(VENV_PYTHON).lower():
    if sys.platform == "win32":
        sys.exit(subprocess.call([str(VENV_PYTHON)] + sys.argv))
    else:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

import webbrowser
import threading
import time

try:
    import uvicorn
except ImportError:
    print("[*] Đang cài đặt các thư viện cần thiết...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(BASE_DIR / "backend" / "requirements.txt")])
    import uvicorn


def is_custom_host_configured(host="nguyencondanh29052007.local"):
    try:
        hosts_path = Path(r"C:\Windows\System32\drivers\etc\hosts") if sys.platform == "win32" else Path("/etc/hosts")
        if hosts_path.exists():
            with open(hosts_path, "r", encoding="utf-8", errors="ignore") as f:
                return host in f.read()
    except Exception:
        return False
    return False

def open_browser():
    time.sleep(1.2)
    if is_custom_host_configured("nguyencondanh29052007.local"):
        url = "http://nguyencondanh29052007.local:8000"
    elif is_custom_host_configured("nguyencondanh29052007.com"):
        url = "http://nguyencondanh29052007.com:8000"
    else:
        url = "http://localhost:8000"
        
    print(f"\n[⚡] Đang mở trình duyệt tại: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Không thể tự động mở trình duyệt: {e}")

def main():
    port = int(os.environ.get("PORT", 8000))
    is_cloud = "PORT" in os.environ or "RENDER" in os.environ

    print("=" * 66)
    print("  🚀 TIKTOK HD DOWNLOADER - DÀNH RIÊNG CHO NGUYỄN CÔNG DANH")
    print(f"  🌐 Đang khởi chạy máy chủ tại cổng (Port): {port}")
    if not is_cloud:
        if is_custom_host_configured("nguyencondanh29052007.local"):
            print("     👉 http://nguyencondanh29052007.local:8000 (Tên miền riêng)")
        if is_custom_host_configured("nguyencondanh29052007.com"):
            print("     👉 http://nguyencondanh29052007.com:8000 (Tên miền riêng .com)")
        print(f"     👉 http://localhost:{port}")
    print("  Nhấn Ctrl+C để dừng ứng dụng")
    print("=" * 66)

    # Start thread to open browser only in local desktop environment
    if not is_cloud:
        threading.Thread(target=open_browser, daemon=True).start()

    # Start FastAPI server listening on all network interfaces
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
