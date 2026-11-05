
import re
import yt_dlp
from datetime import datetime, timezone


SHORTS_CUTOFF = datetime(
    2024, 10, 15, tzinfo=timezone.utc
)


def check_video(video_id):

    video_id = video_id.strip()

    if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", video_id):
        raise ValueError("Video ID phải gồm 11 ký tự!")

    url = f"https://www.youtube.com/watch?v={video_id}"

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extractor_retries": 2,
        "socket_timeout": 20
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    duration = int(info.get("duration") or 0)
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)

    upload_date = info.get("upload_date")

    published_at = None

    if upload_date:
        published_at = datetime.strptime(
            upload_date, "%Y%m%d"
        ).replace(tzinfo=timezone.utc)

    # Phân loại
    if duration <= 0 or width <= 0 or height <= 0:
        video_type = "UNKNOWN"

    elif duration > 180:
        video_type = "VIDEO_THUONG"

    elif width > height:
        video_type = "VIDEO_THUONG"

    elif published_at is None:
        video_type = "UNKNOWN"

    elif published_at < SHORTS_CUTOFF:
        video_type = "VIDEO_THUONG"

    else:
        video_type = "SHORTS"

    return {
        "video_id": video_id,
        "title": info.get("title"),
        "channel": info.get("channel"),
        "channel_id": info.get("channel_id"),
        "duration_seconds": duration,
        "resolution": f"{width}x{height}",
        "aspect_ratio": round(width / height, 3) if height else None,
        "upload_date": upload_date,
        "type": video_type,
        "url": url
    }


if __name__ == "__main__":

    print("=" * 45)
    print("       YOUTUBE SHORTS CHECKER")
    print("=" * 45)

    video_id = input("\nNhập Video ID: ").strip()

    try:

        result = check_video(video_id)

        print("\n========== VIDEO INFO ==========")

        for key, value in result.items():
            print(f"{key}: {value}")

        print("\n========== CLASSIFICATION ==========")

        if result["type"] == "SHORTS":
            print("KẾT LUẬN: VIDEO SHORTS")

        elif result["type"] == "VIDEO_THUONG":
            print("KẾT LUẬN: VIDEO THƯỜNG")

        else:
            print("KẾT LUẬN: UNKNOWN")

    except Exception as e:
        print("\nERROR:", e)
