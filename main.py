import sys
import os
import webview
from src.web_api import WebBridgeApi
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def main():
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
    logger.info("Starting pywebview with modern Cyber-Dark HTML5/CSS3 frontend...")
    webview.start(debug=False)


if __name__ == "__main__":
    main()

