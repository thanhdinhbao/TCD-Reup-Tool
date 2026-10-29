"""Background Automation Worker Thread for TCD REUP TOOL."""
import os
import re
import logging
from typing import List, Optional, Dict, Any
from PyQt5.QtCore import QThread, pyqtSignal
import json
from src.services.youtube_downloader import YouTubeDownloader, DownloadConfig
from src.services.video_processor import VideoProcessor, VideoProcessConfig
from src.services.tiktok_uploader import TikTokUploader
from src.services.telegram_notifier import TelegramNotifier
from src.services.youtube_api import APIKeyManager
from src.services.schedule_analyzer import YouTubeScheduleAnalyzer

logger = logging.getLogger(__name__)


class AutomationWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    queue_add_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(
        self,
        channels: List[str],
        base_path: str,
        auto_upload_tiktok: bool = False,
        gpm_port: str = "9222",
        telegram_notifier: Optional[TelegramNotifier] = None,
        api_key_manager: Optional[APIKeyManager] = None,
        schedule: Optional[List[Dict[str, str]]] = None,
        tiktok_config: Optional[Dict[str, Any]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.channels = channels
        self.base_path = base_path
        self.auto_upload_tiktok = auto_upload_tiktok
        self.gpm_port = gpm_port or "9222"
        self.telegram_notifier = telegram_notifier
        self.api_key_manager = api_key_manager
        self.schedule = schedule or []
        self.tiktok_config = tiktok_config or {}
        self._is_running = True

    def stop(self):
        """Request the worker thread to stop processing."""
        self._is_running = False

    def run(self):
        self.log_signal.emit("Bắt đầu khởi tạo luồng tự động hóa đa kênh...")
        self.progress_signal.emit(5)
        if self.api_key_manager and self.api_key_manager.get_keys():
            k_count = len(self.api_key_manager.get_keys())
            self.log_signal.emit(f"Đã nạp {k_count} YouTube Data API Key để tối ưu hóa hạn mức.")

        # Check schedule for GPM
        if self.schedule:
            in_window = YouTubeScheduleAnalyzer.is_current_time_in_schedule(self.schedule)
            slots_str = ", ".join(f"{s['start']}-{s['end']}" for s in self.schedule)
            if not in_window:
                self.log_signal.emit(f"⏰ Đang ngoài khung giờ lịch tự động ({slots_str}). GPM sẽ tạm đóng để tiết kiệm RAM.")
            else:
                self.log_signal.emit(f"⏰ Trong khung giờ lịch tự động ({slots_str})! Sẵn sàng kích hoạt GPM upload TikTok.")

        downloads_dir = os.path.join(self.base_path, "downloads")
        output_dir = os.path.join(self.base_path, "output")
        os.makedirs(downloads_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        watermark_candidates = [
            os.path.join(self.base_path, "assets", "watermark.png"),
            os.path.join(self.base_path, "watermark.png"),
            os.path.join(self.base_path, "assets", "icon.png"),
            os.path.join(self.base_path, "icon.png"),
        ]
        watermark_path = next((p for p in watermark_candidates if os.path.exists(p)), None)

        downloader = YouTubeDownloader(DownloadConfig(output_dir=downloads_dir))
        processor = VideoProcessor(VideoProcessConfig(output_folder=output_dir, watermark_path=watermark_path))
        uploader = TikTokUploader(remote_debugging_address=f"127.0.0.1:{self.gpm_port}")

        # Load channel-specific API key mapping if available
        map_file = os.path.join(self.base_path, "config", "channel_api_map.json")
        if not os.path.exists(map_file):
            map_file = os.path.join(self.base_path, "channel_api_map.json")
        channel_keys_map = {}
        if os.path.exists(map_file):
            try:
                with open(map_file, "r", encoding="utf-8") as f:
                    raw_map = json.load(f)
                    for proj, chs in raw_map.items():
                        for u, keys in chs.items():
                            channel_keys_map[u] = keys
            except Exception:
                pass

        total_channels = len(self.channels)
        total_processed = 0

        for ch_idx, raw_ch in enumerate(self.channels):
            if not self._is_running:
                break

            ch_url = re.sub(r"^[^\w@/:]+", "", raw_ch).strip()
            assigned_k = channel_keys_map.get(ch_url, [])
            if assigned_k:
                self.log_signal.emit(f"[{ch_idx+1}/{total_channels}] Quét kênh: {ch_url} (Áp dụng {len(assigned_k)} API Keys chuyên dụng)...")
            else:
                self.log_signal.emit(f"[{ch_idx+1}/{total_channels}] Đang quét video mới từ kênh: {ch_url}...")
            self.progress_signal.emit(10 + int((ch_idx / max(total_channels, 1)) * 20))

            videos = downloader.get_channel_videos(ch_url, limit=3)
            if not videos:
                self.log_signal.emit(f"Không trích xuất được video nào trên kênh {ch_url}.")
                continue

            self.log_signal.emit(f"Tìm thấy {len(videos)} video trên kênh {ch_url}.")

            for v_idx, v in enumerate(videos):
                if not self._is_running:
                    break

                title = v.get("title", f"Video_{v_idx}")
                vid_id = v.get("id", f"id_{v_idx}")
                vid_url = v.get("url", f"https://www.youtube.com/watch?v={vid_id}")

                safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).rstrip()[:40].strip() or "video"
                raw_filename = f"{safe_title}_{vid_id}.mp4"
                raw_path = os.path.join(downloads_dir, raw_filename)
                render_filename = f"{safe_title}_{vid_id}_tiktok.mp4"
                render_path = os.path.join(output_dir, render_filename)

                self.queue_add_signal.emit(f"⏳ [Đang xử lý] {title[:40]}... (ID: {vid_id})")
                self.log_signal.emit(f"Đang tải video YouTube: {title} ({vid_id})...")
                self.progress_signal.emit(35)

                ok_dl = downloader.download_video(vid_url, raw_path)
                if not ok_dl or not os.path.exists(raw_path):
                    self.log_signal.emit(f"Lỗi: Không tải được video {vid_id} từ {vid_url}.")
                    continue

                self.log_signal.emit(f"Tải xong file gốc: {os.path.basename(raw_path)}")
                self.log_signal.emit("Bắt đầu render video định dạng dọc 9:16 bằng FFmpeg...")
                self.progress_signal.emit(65)

                # Find profile bound to this channel
                bound_prof = None
                for prof in self.tiktok_config.get("profiles", []):
                    if ch_url in prof.get("assigned_channels", []):
                        bound_prof = prof
                        break

                # Determine render resolution
                render_w, render_h = 720, 1280
                if bound_prof:
                    r_mode = bound_prof.get("render_mode", "")
                    if "360p" in r_mode.lower():
                        render_w, render_h = 360, 640
                    elif "1080p" in r_mode.lower():
                        render_w, render_h = 1080, 1920

                ok_render = processor.render_for_tiktok(
                    input_path=raw_path,
                    output_path=render_path,
                    width=render_w,
                    height=render_h,
                    watermark_path=watermark_path
                )

                if not ok_render or not os.path.exists(render_path):
                    self.log_signal.emit(f"Lỗi: Render thất bại file {raw_filename}.")
                    continue

                self.log_signal.emit(f"Render video thành công ({render_w}x{render_h}): {os.path.basename(render_path)}")
                total_processed += 1
                self.progress_signal.emit(85)

                if self.auto_upload_tiktok:
                    target_gpm_id = bound_prof.get("profile_id", "") if bound_prof else ""
                    target_name = bound_prof.get("profile_name", "Mặc định") if bound_prof else "Mặc định"
                    self.log_signal.emit(f"Đang kết nối GPM Profile [{target_name}] (ID: {target_gpm_id[:8]}...) qua CDP Port {self.gpm_port}...")

                    # Format caption
                    cap_mode = self.tiktok_config.get("caption_mode", "")
                    final_caption = title
                    if "hashtag" in cap_mode.lower():
                        final_caption = f"{title} #fyp #viral #trending"

                    ok_upload = uploader.upload_video(render_path, caption=final_caption, auto_post=False)
                    if ok_upload:
                        self.log_signal.emit(f"Tải lên TikTok Studio thành công qua Profile [{target_name}]: {title}")
                    else:
                        self.log_signal.emit(
                            f"Cảnh báo: Không thể upload tự động qua CDP Port {self.gpm_port}. File sẵn sàng tại: {render_path}"
                        )

                if self.telegram_notifier and self.telegram_notifier.enabled:
                    self.telegram_notifier.send_message(
                        f"✨ <b>TCD REUP TOOL — Video Đã Xử Lý</b>\n"
                        f"🎬 Tiêu đề: <b>{title}</b>\n"
                        f"💾 File: <code>{render_filename}</code>\n"
                        f"📁 Thư mục: <code>output/</code>"
                    )

                self.progress_signal.emit(100)

        if self._is_running:
            self.log_signal.emit(f"Hoàn thành tự động hóa! Đã xử lý thành công {total_processed} video.")
        else:
            self.log_signal.emit("Tiến trình đã được dừng bởi người dùng.")

        self.finished_signal.emit()
