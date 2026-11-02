import os
import sys
import shutil
import subprocess

def build():
    print("=== BAT DAU BUILD EXE CHO TCD-REUP TOOL ===")
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    # Don dep thu muc build & dist cu neu co
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"Cleaning: {folder}...")
            shutil.rmtree(folder, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "TCD-Reup",
        "--icon", os.path.join("assets", "icon.ico"),
        "--add-data", f"{os.path.join('src', 'web')};src/web",
        "--add-data", f"assets;assets",
        "--collect-all", "pywebview",
        "--collect-all", "pythonnet",
        "--collect-all", "clr_loader",
        "--collect-all", "yt_dlp",
        "--hidden-import", "clr",
        "--hidden-import", "pythonnet",
        "--hidden-import", "bottle",
        "--hidden-import", "proxy_tools",
        "--hidden-import", "webview.platforms.winforms",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "googleapiclient",
        "--hidden-import", "googleapiclient.discovery",
        "--hidden-import", "googleapiclient.errors",
        "--hidden-import", "cryptography",
        "--hidden-import", "selenium",
        "--hidden-import", "selenium.webdriver",
        "main.py"
    ]

    print("\nRunning PyInstaller...")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("\n[ERROR] PyInstaller build failed!")
        sys.exit(result.returncode)

    dist_app_dir = os.path.join(root_dir, "dist", "TCD-Reup")
    print(f"\n[OK] Build completed at: {dist_app_dir}")

    # Copy config and sample data
    for d in ["config", "projects", "downloads", "output"]:
        src_d = os.path.join(root_dir, d)
        dst_d = os.path.join(dist_app_dir, d)
        if os.path.exists(src_d):
            print(f"Copying {d} to dist...")
            shutil.copytree(src_d, dst_d, dirs_exist_ok=True)
        else:
            os.makedirs(dst_d, exist_ok=True)

    print("\n=== BUILD HOAN TAT ===")
    print("Executable location:", os.path.join(dist_app_dir, "TCD-Reup.exe"))

if __name__ == "__main__":
    build()
