
import time
import shutil
import subprocess
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

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
    ffmpeg = shutil.which("ffmpeg")

    long_side_map = {360: 640, 480: 854, 720: 1280, 1080: 1920, 1440: 2560, 2160: 3840}
    max_long = long_side_map.get(max_height, int(max_height * 16 / 9) if max_height else None)

    if max_height:
        v_format = f"bestvideo[width<={max_long}][height<={max_long}]/bestvideo[height<={max_height}]/bestvideo"
        v_sort = [f"res:{max_height}", "+vcodec:avc"]
    else:
        v_format = "bestvideo"
        v_sort = ["+vcodec:avc"]
    a_format = "bestaudio"

    print(f"\nURL: {url}")
    print(
        "Độ phân giải tối đa:",
        f"{max_height}p" if max_height else "Cao nhất",
    )
    print(f"Thư mục lưu: {DOWNLOAD_DIR.resolve()}")
    print("Đang tải song song 2 luồng độc lập (Video + Audio) bằng yt-dlp...\n")

    # 1. Thử tải 2 thread song song độc lập nếu có FFmpeg
    if ffmpeg:
        temp_id = int(time.time() * 1000)
        temp_v = DOWNLOAD_DIR / f"_temp_v_{temp_id}.mp4"
        temp_a = DOWNLOAD_DIR / f"_temp_a_{temp_id}.m4a"

        opts_common = {
            "noplaylist": True,
            "continuedl": True,
            "retries": 10,
            "fragment_retries": 10,
            "concurrent_fragment_downloads": 32,
            "windowsfilenames": True,
            "overwrites": True,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
        }

        opts_v = dict(opts_common)
        opts_v["format"] = v_format
        opts_v["format_sort"] = v_sort
        opts_v["outtmpl"] = str(temp_v)

        opts_a = dict(opts_common)
        opts_a["format"] = a_format
        opts_a["outtmpl"] = str(temp_a)

        try:
            video_info = {}

            def dl_v_worker():
                with yt_dlp.YoutubeDL(opts_v) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info:
                        video_info.update(info)

            def dl_a_worker():
                with yt_dlp.YoutubeDL(opts_a) as ydl:
                    ydl.download([url])

            with ThreadPoolExecutor(max_workers=2) as pool:
                f_v = pool.submit(dl_v_worker)
                f_a = pool.submit(dl_a_worker)
                f_v.result()
                f_a.result()

            raw_title = video_info.get("title", "video")
            vid_id = video_info.get("id", "vid")
            safe_title = "".join(c for c in raw_title if c not in r'<>:"/\\|?*').strip()[:100]
            final_path = DOWNLOAD_DIR / f"{safe_title} [{vid_id}].mp4"

            print("Đã tải xong 2 luồng độc lập, đang ghép video bằng FFmpeg...")
            t_merge_start = time.perf_counter()
            merge_cmd = [
                ffmpeg, "-y",
                "-i", str(temp_v),
                "-i", str(temp_a),
                "-c", "copy",
                "-movflags", "+faststart",
                str(final_path)
            ]
            subprocess.run(merge_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            t_merge = time.perf_counter() - t_merge_start

            if temp_v.exists():
                temp_v.unlink()
            if temp_a.exists():
                temp_a.unlink()

            print("\n========== HOÀN TẤT ==========")
            print(
                f"Tổng thời gian: {format_time(time.perf_counter() - start)} "
                f"(FFmpeg merge: {t_merge:.2f}s)"
            )
            print(f"Thư mục: {DOWNLOAD_DIR.resolve()}")
            print(f"File: {final_path.name}")
            return

        except KeyboardInterrupt:
            if temp_v.exists():
                temp_v.unlink()
            if temp_a.exists():
                temp_a.unlink()
            print("\nĐã dừng tải. Có thể chạy lại để tiếp tục.")
            return

        except Exception as exc:
            print(f"\n2 luồng song song gặp lỗi, chuyển sang tải tuần tự truyền thống: {exc}")
            if temp_v.exists():
                temp_v.unlink()
            if temp_a.exists():
                temp_a.unlink()

    # 2. Fallback tuần tự nếu không có ffmpeg hoặc 2 luồng lỗi
    if max_height is None:
        format_selector = "bestvideo*+bestaudio/best"
        sort_selector = ["+vcodec:avc"]
    else:
        format_selector = (
            f"bestvideo[width<={max_long}][height<={max_long}]+bestaudio/"
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[width<={max_long}][height<={max_long}]/best"
        )
        sort_selector = [f"res:{max_height}", "+vcodec:avc"]

    options = {
        "format": format_selector,
        "format_sort": sort_selector,
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
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg

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
