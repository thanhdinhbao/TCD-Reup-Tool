
import time
import shutil
from pathlib import Path
from datetime import timedelta

import yt_dlp


DOWNLOAD_DIR = Path.cwd() / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

RESOLUTIONS = {
    "1": ("360p", 360),
    "2": ("480p", 480),
    "3": ("720p HD", 720),
    "4": ("1080p Full HD", 1080),
    "5": ("1440p 2K", 1440),
    "6": ("2160p 4K", 2160),
    "7": ("Cao nhất có thể", None),
}


def format_time(seconds):
    if seconds is None:
        return "--:--"

    return str(timedelta(seconds=max(0, int(seconds))))


def progress_hook(data):
    status = data.get("status")

    if status == "downloading":
        downloaded = data.get("downloaded_bytes", 0)
        total = data.get("total_bytes") or data.get(
            "total_bytes_estimate"
        )

        speed = data.get("speed")
        eta = data.get("eta")

        if total:
            percent = downloaded / total * 100
            width = 28
            filled = int(width * percent / 100)
            bar = "#" * filled + "-" * (width - filled)

            progress = (
                f"[{bar}] {percent:6.2f}% "
                f"{downloaded / 1048576:.1f}/"
                f"{total / 1048576:.1f} MB"
            )
        else:
            progress = (
                f"Đã tải {downloaded / 1048576:.1f} MB"
            )

        speed_text = (
            f"{speed / 1048576:.2f} MB/s"
            if speed else "Đang tính..."
        )

        print(
            f"\r{progress} | {speed_text} "
            f"| ETA {format_time(eta)}".ljust(150),
            end="",
            flush=True,
        )

    elif status == "finished":
        print("\nĐã tải xong dữ liệu, đang ghép video...")


def choose_resolution():
    print("\n========== CHỌN ĐỘ PHÂN GIẢI ==========")

    for key, (label, _) in RESOLUTIONS.items():
        print(f"{key}. {label}")

    while True:
        choice = input("Chọn độ phân giải (1-7): ").strip()

        if choice in RESOLUTIONS:
            return RESOLUTIONS[choice][1]

        print("Lựa chọn không hợp lệ. Vui lòng chọn từ 1 đến 7.")


def download_video(url, max_height):
    start = time.perf_counter()

    # Giới hạn độ phân giải video, vẫn lấy âm thanh tốt nhất.
    if max_height is None:
        format_selector = (
            "bestvideo*+bestaudio/best"
        )
    else:
        format_selector = (
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]"
        )

    options = {
        "format": format_selector,
        "outtmpl": str(
            DOWNLOAD_DIR / "%(title).180B [%(id)s].%(ext)s"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "continuedl": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 32,
        "progress_hooks": [progress_hook],
        "windowsfilenames": True,
        "overwrites": False,
        "quiet": True,
        "no_warnings": False,
    }

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg

    print(f"\nURL: {url}")
    print(
        "Độ phân giải tối đa:",
        f"{max_height}p" if max_height else "Cao nhất",
    )
    print(f"Thư mục lưu: {DOWNLOAD_DIR.resolve()}")
    print("Đang tải...\n")

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        print("\n\n========== HOÀN TẤT ==========")
        print(
            f"Tổng thời gian: "
            f"{format_time(time.perf_counter() - start)}"
        )
        print(f"Thư mục: {DOWNLOAD_DIR.resolve()}")

    except KeyboardInterrupt:
        print("\nĐã dừng tải. Có thể chạy lại để tiếp tục.")

    except Exception as exc:
        print(f"\nLỗi tải video: {exc}")
        print(
            f"Thời gian đã chạy: "
            f"{format_time(time.perf_counter() - start)}"
        )


def main():
    print("=" * 48)
    print("       FAST VIDEO DOWNLOADER")
    print("              Powered by yt-dlp")
    print("=" * 48)

    while True:
        try:
            url = input(
                "\nDán link video (Enter để thoát): "
            ).strip()

            if not url:
                break

            resolution = choose_resolution()
            download_video(url, resolution)

        except KeyboardInterrupt:
            print("\nĐã thoát chương trình.")
            break


if __name__ == "__main__":
    main()
