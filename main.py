import sys
import os
import webview
from src.web_api import WebBridgeApi
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def _unblock_paths():
    """Tự động gỡ bỏ cờ chặn bảo mật Windows (Zone.Identifier / Mark of the Web) cho các DLL."""
    if sys.platform != "win32":
        return
    dirs_to_check = []
    if hasattr(sys, '_MEIPASS'):
        dirs_to_check.append(sys._MEIPASS)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        dirs_to_check.append(exe_dir)
        internal_dir = os.path.join(exe_dir, "_internal")
        if os.path.exists(internal_dir):
            dirs_to_check.append(internal_dir)

    for base in dirs_to_check:
        try:
            for root, _, files in os.walk(base):
                for f in files:
                    if f.lower().endswith((".dll", ".exe", ".pyd")):
                        fp = os.path.join(root, f)
                        zone = f"{fp}:Zone.Identifier"
                        try:
                            if os.path.exists(zone):
                                os.remove(zone)
                        except Exception:
                            pass
        except Exception:
            pass


def main():
    _unblock_paths()
    if getattr(sys, 'frozen', False):
        asset_base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
        data_base = os.path.dirname(sys.executable)
    else:
        asset_base = os.path.dirname(os.path.abspath(__file__))
        data_base = asset_base

    html_path = os.path.join(asset_base, "src", "web", "index.html")
    if not os.path.exists(html_path):
        html_path = os.path.join(data_base, "src", "web", "index.html")

    if not os.path.exists(html_path):
        logger.error(f"HTML entry not found at: {html_path}")
        return

    bridge = WebBridgeApi(base_path=data_base)

    window = webview.create_window(
        title="TCD REUP TOOL | License Vĩnh viễn | Thanh Code Dao @thanhcodedao",
        url=html_path,
        js_api=bridge,
        width=1240,
        height=840,
        min_size=(1080, 720),
        background_color="#0B0F19"
    )

    bridge.set_window(window)
    logger.info("Starting application...")
    webview.start(debug=False)


if __name__ == "__main__":
    main()

