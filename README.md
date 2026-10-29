# TCD REUP TOOL - Reconstructed & Modernized

Hệ thống tự động hóa đa kênh YouTube & TikTok Studio tích hợp GPMLogin CDP.

## Cấu trúc thư mục chuẩn (Project Architecture)

```text
TCD-Crack/
├── TCD_VIP_PRO.exe            # Binary gốc (Reverse engineered reference)
└── Reconstructed/
    ├── assets/                # Tài nguyên đồ họa (icons, watermarks)
    │   ├── icon.ico
    │   ├── icon.png
    │   └── watermark.png
    │
    ├── config/                # Toàn bộ cấu hình hệ thống (.json)
    │   ├── api_pool.json           # Kho YouTube API v3 keys
    │   ├── channel_api_map.json    # Phân phối keys cho từng kênh
    │   ├── api_history.json        # Lịch sử xoay vòng & phân bổ key
    │   ├── gpm_profiles_cache.json # Bộ nhớ đệm GPM profiles
    │   ├── projects_config.json    # Cấu hình dự án hoạt động
    │   └── telegram_config.json    # Cấu hình bot token & chat IDs
    │
    ├── projects/              # File cấu hình riêng biệt cho từng dự án
    │   └── 1232.json
    │
    ├── downloads/             # Thư mục lưu tạm video tải về từ YouTube
    ├── output/                # Thư mục xuất video sau xử lý
    │
    ├── src/                   # Mã nguồn chính
    │   ├── core/              # Quản lý license, dự án, background worker
    │   │   ├── license_verify.py
    │   │   ├── project_manager.py
    │   │   └── worker.py
    │   │
    │   ├── services/          # Các dịch vụ cốt lõi
    │   │   ├── api_pool_manager.py     # Quản lý kho 300+ YouTube API keys
    │   │   ├── gpm_api_client.py       # Kết nối GPMLogin Local API (Port 9495)
    │   │   ├── schedule_analyzer.py    # Phân tích khung giờ vàng upload
    │   │   ├── telegram_notifier.py    # Báo cáo tiến trình qua Telegram
    │   │   ├── tiktok_uploader.py      # Điều khiển CDP upload TikTok Studio
    │   │   ├── video_processor.py      # FFmpeg 9:16 vertical & 61s extender
    │   │   ├── youtube_api.py          # Google YouTube Data API v3 client
    │   │   └── youtube_downloader.py   # yt-dlp đa luồng 16 fragments
    │   │
    │   ├── ui/                # Giao diện PyQt5 fallback
    │   │   ├── api_distributor_dialog.py
    │   │   ├── main_window.py
    │   │   ├── schedule_dialogs.py
    │   │   ├── theme.py
    │   │   └── tiktok_config_dialog.py
    │   │
    │   ├── utils/             # Tiện ích logging & helpers
    │   │   └── logger.py
    │   │
    │   ├── web/               # Giao diện hiện đại Cyber-Dark HTML5/CSS3/JS
    │   │   ├── app.js
    │   │   ├── index.html
    │   │   └── styles.css
    │   │
    │   └── web_api.py         # Cầu nối Pywebview Bridge (Python <-> JS)
    │
    ├── tests/                 # Bộ kiểm thử tự động (Unit Tests)
    │   ├── test_core.py
    │   └── test_worker.py
    │
    ├── main.py                # Điểm khởi động chính (Mặc định mở Pywebview)
    ├── main_webview.py        # Khởi chạy trực tiếp giao diện Pywebview HTML5
    └── requirements.txt       # Danh sách thư viện phụ thuộc
```

## Hướng dẫn cài đặt & khởi chạy

1. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```

2. Khởi chạy giao diện chính:
   ```bash
   python main.py
   # hoặc:
   python main_webview.py
   ```
   *(Để chạy giao diện PyQt5 cũ: `python main.py --qt`)*

3. Chạy toàn bộ bài kiểm tra:
   ```bash
   python -m unittest discover -s tests
   ```

