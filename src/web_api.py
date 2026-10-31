"""
Web API Bridge for pywebview interface.
Exposes full backend capabilities to HTML/JS frontend:
- ProjectManager (create, switch, delete, manage schedules)
- APIPoolManager (pool editing, bulk channel distribution, multi-thread test)
- GPMLocalAPIClient (sync profiles from port 9495, start/stop profiles)
- YouTubeScheduleAnalyzer (cluster_times_multi, cluster_times_single)
- AutomationWorker (run download & upload in background thread, emit logs)
- TelegramNotifier (test message, save config)
"""
import os
import re
import time
import json
import logging
import threading
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.core.project_manager import ProjectManager
from src.services.api_pool_manager import APIPoolManager
from src.services.gpm_api_client import GPMLocalAPIClient
from src.services.schedule_analyzer import YouTubeScheduleAnalyzer
from src.services.telegram_notifier import TelegramNotifier
from src.services.youtube_api import APIKeyManager, YouTubeAPIClient
from src.services.youtube_downloader import YouTubeDownloader, DownloadConfig
from src.services.video_processor import VideoProcessor, VideoProcessConfig
from src.services.tiktok_uploader import TikTokUploader

logger = logging.getLogger(__name__)


class WebBridgeApi:
    """JS API Bridge exposed to window.pywebview.api.
    
    NOTE: All internal fields MUST start with an underscore ('_') so that
    pywebview does not recursively introspect complex objects (such as Window,
    WinForms Form, or .NET AccessibilityObject) which causes maximum recursion depth exceeded.
    """

    def __init__(self, base_path: str):
        self._base_path = base_path
        self._config_dir = os.path.join(self._base_path, "config")
        os.makedirs(self._config_dir, exist_ok=True)

        self._window = None  # Injected after webview.create_window
        self._project_manager = ProjectManager(self._base_path)
        self._api_pool = APIPoolManager(self._base_path)
        self._gpm_client = GPMLocalAPIClient()

        key_cfg = os.path.join(self._config_dir, "api_keys.json")
        if not os.path.exists(key_cfg) and os.path.exists(os.path.join(self._base_path, "api_keys.json")):
            key_cfg = os.path.join(self._base_path, "api_keys.json")
        self._api_key_manager = APIKeyManager(config_path=key_cfg)

        self._telegram_config_path = os.path.join(self._config_dir, "telegram_config.json")
        if not os.path.exists(self._telegram_config_path) and os.path.exists(os.path.join(self._base_path, "telegram_config.json")):
            self._telegram_config_path = os.path.join(self._base_path, "telegram_config.json")
        self._telegram = TelegramNotifier()
        self._telegram.load_telegram_map(self._telegram_config_path)

        self._is_worker_running = False
        self._worker_thread = None

    def set_window(self, window):
        self._window = window

    def _eval_js(self, script: str):
        if self._window:
            try:
                self._window.evaluate_js(script)
            except Exception as e:
                logger.error(f"Error evaluating JS: {e}")

    def emit_log(self, text: str):
        """Send timestamped log line to frontend terminal."""
        clean_text = text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
        self._eval_js(f"window.onAppLog('{clean_text}')")

    def emit_queue_item(self, vid_id: str, title: str, progress: int, status: str):
        """Update download/render queue table in frontend."""
        item = {
            "id": vid_id,
            "title": title,
            "progress": progress,
            "status": status
        }
        item_json = json.dumps(item).replace("'", "\\'")
        self._eval_js(f"window.onQueueUpdate('{item_json}')")

    # ==========================================
    # GPM PROFILES LOCAL CACHING
    # ==========================================

    def _get_all_gpm_profiles(self) -> List[Dict[str, Any]]:
        cache_path = os.path.join(self._config_dir, "gpm_profiles_cache.json")
        if not os.path.exists(cache_path) and os.path.exists(os.path.join(self._base_path, "gpm_profiles_cache.json")):
            cache_path = os.path.join(self._base_path, "gpm_profiles_cache.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if isinstance(cached, list) and len(cached) > 0:
                        return cached
            except Exception:
                pass

        # Try live query
        try:
            profiles = self._gpm_client.list_profiles(page_size=100)
            if profiles:
                self._save_cached_gpm_profiles(profiles)
                return profiles
        except Exception:
            pass

        # Fallback default sample profiles
        defaults = [
            {"id": "143b087-6777-412b-8287-069b806425e3", "name": "New profile 015"},
            {"id": "37f783ac-2635-4d53-ab8d-a300c790ecdc", "name": "Profile 01"},
            {"id": "98a123bc-4567-8901-cdef-123456789abc", "name": "TikTok VIP Channel 1"},
            {"id": "55b432de-1234-5678-abcd-987654321fed", "name": "TikTok VIP Channel 2"},
        ]
        self._save_cached_gpm_profiles(defaults)
        return defaults

    def _save_cached_gpm_profiles(self, profiles: List[Dict[str, Any]]):
        cache_path = os.path.join(self._config_dir, "gpm_profiles_cache.json")
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving GPM profiles cache: {e}")

    # ==========================================
    # APP INITIALIZATION & STATE
    # ==========================================

    def get_initial_state(self) -> Dict[str, Any]:
        """Returns full initial state needed by the web UI."""
        active_proj = self._project_manager.active_project
        pdata = self._project_manager.load_project(active_proj)

        return {
            "active_project": active_proj,
            "projects": self._project_manager.list_projects(),
            "channels": pdata.get("channels", []),
            "threads": pdata.get("threads", 500),
            "use_proxy": pdata.get("use_proxy", False),
            "proxy_region": pdata.get("proxy_region", "IP - Nhật Bản"),
            "auto_upload_tiktok": pdata.get("auto_upload_tiktok", True),
            "only_shorts": pdata.get("only_shorts", True),
            "telegram_enabled": self._telegram.enabled,
            "telegram_token": self._telegram.bot_token,
            "telegram_chat_ids": self._telegram.telegram_chat_ids,
            "pool_total": self._api_pool.get_total_count(),
            "pool_remaining": self._api_pool.get_remaining_count(),
            "dead_keys_count": len(self._api_pool.dead_keys),
            "schedule": pdata.get("schedule", []),
            "schedule_mode": pdata.get("schedule_mode", "multi"),
            "tiktok_config": self._project_manager.get_tiktok_config(active_proj),
            "gpm_profiles": self._get_all_gpm_profiles()
        }

    # ==========================================
    # PROJECT MANAGEMENT
    # ==========================================

    def create_project(self, name: str) -> Dict[str, Any]:
        success = self._project_manager.create_project(name)
        if success:
            self.emit_log(f"✨ Đã tạo và kích hoạt dự án mới: <b>{name}</b>")
        return {
            "success": success,
            "active_project": self._project_manager.active_project,
            "projects": self._project_manager.list_projects()
        }

    def switch_project(self, name: str) -> Dict[str, Any]:
        success = self._project_manager.switch_project(name)
        pdata = self._project_manager.load_project(name)
        if success:
            self.emit_log(f"📁 Đã chuyển sang dự án: <b>{name}</b> ({len(pdata.get('channels', []))} kênh)")
        return {
            "success": success,
            "active_project": self._project_manager.active_project,
            "channels": pdata.get("channels", []),
            "schedule": pdata.get("schedule", []),
            "tiktok_config": self._project_manager.get_tiktok_config(name)
        }

    def delete_project(self, name: str) -> Dict[str, Any]:
        success = self._project_manager.delete_project(name)
        if success:
            self.emit_log(f"🗑 Đã xóa dự án: <b>{name}</b>")
        return {
            "success": success,
            "active_project": self._project_manager.active_project,
            "projects": self._project_manager.list_projects()
        }

    def save_project_state(self, state: Dict[str, Any]) -> bool:
        """Save channel list, proxy, threads for active project."""
        proj = self._project_manager.active_project
        pdata = self._project_manager.load_project(proj)
        pdata["channels"] = state.get("channels", pdata.get("channels", []))
        pdata["threads"] = state.get("threads", 500)
        pdata["use_proxy"] = state.get("use_proxy", False)
        pdata["proxy_region"] = state.get("proxy_region", "IP - Nhật Bản")
        pdata["auto_upload_tiktok"] = state.get("auto_upload_tiktok", True)
        pdata["only_shorts"] = state.get("only_shorts", True)
        return self._project_manager.save_project(proj, pdata)

    # ==========================================
    # SCHEDULE ANALYSIS
    # ==========================================

    def analyze_schedule(self, mode: str) -> Dict[str, Any]:
        proj = self._project_manager.active_project
        pdata = self._project_manager.load_project(proj)
        channels = pdata.get("channels", [])

        # Chỉ sử dụng các API key được cấp phát riêng cho từng kênh trong Quản lý Key
        channel_key_map = self._api_pool.channel_map.get(proj, {})

        analyzer = YouTubeScheduleAnalyzer()
        schedules = analyzer.analyze(channels, mode=mode, channel_key_map=channel_key_map)

        pdata["schedule"] = schedules
        pdata["schedule_mode"] = mode
        self._project_manager.save_project(proj, pdata)

        slots_str = ", ".join(f"{s['start']}-{s['end']}" for s in schedules) if schedules else "Chạy 24/7"
        if mode == "all_time":
            mode_label = "QUÉT TẤT CẢ THỜI GIAN (24/7)"
        elif mode == "multi":
            mode_label = "TÁCH CỤM (Khuyên dùng)"
        else:
            mode_label = "GỘP TẤT CẢ"
        self.emit_log(f"⏰ Phân tích lịch đăng thành công chế độ [{mode_label}]. Tìm thấy {len(schedules)} khung giờ: {slots_str}")
        return {
            "success": True,
            "schedule": schedules,
            "mode": mode,
            "summary": slots_str
        }

    def save_manual_schedule(self, schedules: List[Dict[str, str]]) -> bool:
        proj = self._project_manager.active_project
        pdata = self._project_manager.load_project(proj)
        pdata["schedule"] = schedules
        res = self._project_manager.save_project(proj, pdata)
        slots_str = ", ".join(f"{s['start']}-{s['end']}" for s in schedules) if schedules else "Chạy 24/7"
        self.emit_log(f"⏰ Đã cập nhật lịch tự động: {slots_str}")
        return res

    # ==========================================
    # API POOL & DISTRIBUTION
    # ==========================================

    def get_api_pool_data(self) -> Dict[str, Any]:
        """Returns API pool stats and scanned TCD channels."""
        projects = self._project_manager.list_projects()
        scanned = []
        for p in projects:
            pdata = self._project_manager.load_project(p)
            for idx, ch in enumerate(pdata.get("channels", [])):
                scanned.append({
                    "folder": f"Folder_{p}_{idx+1}",
                    "channel_url": ch,
                    "project": p,
                    "assigned_keys_count": len(self._api_pool.channel_map.get(p, {}).get(ch, []))
                })

        return {
            "total_keys": self._api_pool.get_total_count(),
            "remaining_keys": self._api_pool.get_remaining_count(),
            "dead_keys_count": len(self._api_pool.dead_keys),
            "master_keys": self._api_pool.master_pool,
            "unassigned_keys": self._api_pool.get_unassigned_keys(),
            "scanned_channels": scanned,
            "last_distribution": self._api_pool.last_distribution_time or "Chưa thực hiện"
        }

    def update_master_pool(self, raw_text: str) -> Dict[str, Any]:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        total, added = self._api_pool.update_pool_keys(lines)
        self.emit_log(f"🔑 Đã cập nhật kho API: {total} keys (Mới thêm: {added})")
        return {"total": total, "added": added}

    def distribute_api_keys(self, mode: str, keys_per_channel: int) -> Dict[str, Any]:
        projects = self._project_manager.list_projects()
        targets = []
        for p in projects:
            pdata = self._project_manager.load_project(p)
            for idx, ch in enumerate(pdata.get("channels", [])):
                targets.append((f"Folder_{p}_{idx+1}", ch, p))

        if mode == "all":
            res = self._api_pool.distribute_all(targets, keys_per_channel)
            self.emit_log(f"🔄 Đã chia lại toàn bộ {res['total_assigned']} API keys đều cho các kênh.")
        else:
            res = self._api_pool.distribute_missing_only(targets, keys_per_channel)
            self.emit_log(f"📥 Đã bù thêm {res['added_keys']} API keys vào các kênh còn thiếu.")

        return res

    def recover_garbage_api_keys(self) -> Dict[str, Any]:
        recovered, affected = self._api_pool.recover_garbage_keys()
        self.emit_log(f"🗑 Đã thu hồi {recovered} API rác/chết từ {affected} kênh.")
        return {"recovered": recovered, "affected": affected}

    def clean_backup_files(self) -> int:
        count = self._api_pool.clean_backup_files()
        self.emit_log(f"🧹 Đã xóa {count} file backup (.bak) tạm.")
        return count

    # ==========================================
    # GPMLOGIN LOCAL API INTEGRATION
    # ==========================================

    def check_gpm_connection(self) -> Dict[str, Any]:
        ok, msg = self._gpm_client.check_connection()
        return {"success": ok, "message": msg, "port": self._gpm_client.port}

    def sync_gpm_profiles(self) -> Dict[str, Any]:
        ok, msg = self._gpm_client.check_connection()
        if ok:
            profiles = self._gpm_client.list_profiles(page_size=100)
            if profiles:
                self._save_cached_gpm_profiles(profiles)
                self.emit_log(f"🚀 Đã đồng bộ {len(profiles)} profiles từ GPMLogin Local API (Port {self._gpm_client.port}).")
                return {"success": True, "profiles": profiles, "message": f"Tìm thấy {len(profiles)} profiles từ GPMLogin."}

        cached = self._get_all_gpm_profiles()
        self.emit_log(f"⚡ Đang nạp {len(cached)} profiles từ bộ nhớ đệm (GPM port {self._gpm_client.port}).")
        return {"success": True, "profiles": cached, "message": f"Chưa kết nối được GPMLogin port {self._gpm_client.port}. Đang dùng {len(cached)} profiles lưu đệm.", "offline": True}

    def test_start_gpm_profile(self, profile_id: str) -> Dict[str, Any]:
        ok, data, msg = self._gpm_client.start_profile(profile_id)
        if ok and isinstance(data, dict):
            port = data.get("remote_debugging_port")
            driver_path = data.get("driver_path", "")
            driver_name = os.path.basename(driver_path) if driver_path else "gpmdriver"
            self.emit_log(f"▶ Khởi động GPM Profile [{profile_id[:8]}...] thành công trên cổng {port} (Driver: {driver_name}).")
            return {"success": True, "port": port, "driver_path": driver_path, "data": data}
        return {"success": False, "message": msg}

    def test_stop_gpm_profile(self, profile_id: str) -> Dict[str, Any]:
        ok, msg = self._gpm_client.stop_profile(profile_id)
        if ok:
            self.emit_log(f"⏹ Đã đóng GPM Profile [{profile_id[:8]}...]")
        return {"success": ok, "message": msg}

    def save_tiktok_config(self, config: Dict[str, Any]) -> bool:
        proj = self._project_manager.active_project
        res = self._project_manager.save_tiktok_config(config, proj)
        if res:
            total_channels = len(config.get("channels_config", {}))
            self.emit_log(f"🚀 Đã lưu cấu hình TikTok Upload cho dự án '{proj}' ({total_channels} kênh được thiết lập).")
        return res

    # ==========================================
    # TELEGRAM
    # ==========================================

    def save_telegram_config(self, token: str, chat_ids_str: str, enabled: bool) -> bool:
        self._telegram.bot_token = token.strip()
        self._telegram.telegram_chat_ids = [c.strip() for c in chat_ids_str.split(",") if c.strip()]
        self._telegram.enabled = enabled
        res = self._telegram.save_telegram_map(self._telegram_config_path)
        status = "BẬT" if enabled else "TẮT"
        self.emit_log(f"📢 Đã lưu cấu hình Telegram: {status}")
        return res

    def test_telegram(self, token: str, chat_ids_str: str) -> Dict[str, Any]:
        c_ids = [c.strip() for c in chat_ids_str.split(",") if c.strip()]
        temp_notif = TelegramNotifier(bot_token=token.strip(), telegram_chat_ids=c_ids, enabled=True)
        ok = temp_notif.send_message("✨ <b>TCD REUP TOOL:</b> Kết nối Telegram Bot thành công qua giao diện Web!")
        return {"success": ok}

    # ==========================================
    # AUTOMATION WORKER ENGINE
    # ==========================================

    def start_automation(self) -> Dict[str, Any]:
        if self._is_worker_running:
            return {"success": False, "message": "Hệ thống đang chạy!"}

        proj = self._project_manager.active_project
        pdata = self._project_manager.load_project(proj)
        channels = pdata.get("channels", [])
        if not channels:
            return {"success": False, "message": "Dự án chưa có kênh YouTube nào!"}

        self._is_worker_running = True
        self._worker_thread = threading.Thread(target=self._run_automation_loop, args=(channels, pdata), daemon=True)
        self._worker_thread.start()

        self.emit_log("▶ Bắt đầu khởi chạy Worker tự động hóa nền...")
        self._eval_js("window.onAutomationStateChange(true)")
        return {"success": True}

    def stop_automation(self) -> Dict[str, Any]:
        self._is_worker_running = False
        self.emit_log("⏹ Đã gửi tín hiệu dừng tự động hóa.")
        self._eval_js("window.onAutomationStateChange(false)")
        return {"success": True}

    def _load_processed_videos(self) -> set:
        path = os.path.join(self._config_dir, "processed_videos.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
            except Exception:
                pass
        return set()

    def _save_processed_videos(self, videos_set: set):
        path = os.path.join(self._config_dir, "processed_videos.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(list(videos_set), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving processed videos: {e}")

    def clear_processed_history(self) -> Dict[str, Any]:
        path = os.path.join(self._config_dir, "processed_videos.json")
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        self.emit_log("🧹 Đã làm mới danh sách video đã đăng.")
        return {"success": True}

    def _run_automation_loop(self, channels: List[str], pdata: Dict[str, Any]):
        downloads_dir = os.path.join(self._base_path, "downloads")
        output_dir = os.path.join(self._base_path, "output")
        os.makedirs(downloads_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        downloader = YouTubeDownloader(DownloadConfig(output_dir=downloads_dir))
        processor = VideoProcessor(VideoProcessConfig(output_folder=output_dir))
        uploader = TikTokUploader()
        schedules = pdata.get("schedule", [])
        tt_cfg = self._project_manager.get_tiktok_config()
        ch_settings = tt_cfg.get("channels_config", {})

        # Check initial schedule status
        if schedules:
            init_status = YouTubeScheduleAnalyzer.get_schedule_status(schedules, prewarm_mins=10)
            slots_str = ", ".join(f"{s['start']}-{s['end']}" for s in schedules)
            self.emit_log(f"⏰ Đã nạp lịch đăng: {slots_str} | Trạng thái hiện tại: {init_status['description']}")

        total = len(channels)
        yt_api = YouTubeAPIClient()
        proj = self._project_manager.active_project
        auto_post_flag = pdata.get("auto_upload_tiktok", True)
        processed_videos = self._load_processed_videos()
        worker_start_time = datetime.now(timezone.utc)
        self.emit_log(f"🚀 [Bật tool] Mốc thời gian kích hoạt: {worker_start_time.strftime('%H:%M:%S UTC')}. Tool CHỈ tải & up video MỚI xuất bản từ thời điểm này trở đi!")
        cycle = 0

        # VÒNG LẶP QUÉT LIÊN TỤC KHÔNG NGHỈ (Chỉ dừng khi người dùng bấm nút Dừng)
        while self._is_worker_running:
            # 1. KIỂM TRA LỊCH ĐĂNG (Tối ưu RAM/CPU & Tự động mở GPM trước giờ đăng)
            sched_status = YouTubeScheduleAnalyzer.get_schedule_status(schedules, prewarm_mins=10)

            def resolve_target_pid():
                for c_url in channels:
                    cfg = ch_settings.get(c_url, {})
                    pid = cfg.get("profile_id", "")
                    if pid:
                        return pid
                for prof in tt_cfg.get("profiles", []):
                    pid = prof.get("profile_id", "")
                    if pid:
                        return pid
                return None

            if sched_status["status"] == "OUTSIDE":
                # Ngoài khung giờ: Tự động đóng GPM Profile để giải phóng RAM & CPU
                if uploader._cached_driver or uploader._cached_profile_id:
                    self.emit_log(f"⏰ [Hết khung giờ] {sched_status['description']}")
                    uploader.close_browser(self._gpm_client)
                    self.emit_log("💤 Đã đóng GPM Profile để tiết kiệm tài nguyên hệ thống.")
                else:
                    if cycle % 6 == 0:
                        self.emit_log(f"💤 [Chờ lịch] {sched_status['description']}")

                # Tạm nghỉ 5s rồi kiểm tra lại đồng hồ (ngắt ngay khi user bấm Dừng)
                for _ in range(5):
                    if not self._is_worker_running:
                        break
                    time.sleep(1)
                cycle += 1
                continue

            elif sched_status["status"] == "APPROACHING":
                # Tới gần giờ đăng (<10 phút): Mở sẵn GPM Profile và chờ video
                target_pid = resolve_target_pid()
                if target_pid and not uploader._cached_driver:
                    self.emit_log(f"⏰ [Gần tới giờ đăng] {sched_status['description']}")
                    self.emit_log(f"🚀 Đang mở sẵn GPM Profile [{target_pid[:8]}...] trên nền để chờ video mới...")
                    uploader.prewarm_profile(target_pid, self._gpm_client)
                    self.emit_log(f"✨ Profile GPM [{target_pid[:8]}...] đã sẵn sàng tại TikTok Studio (0s trễ)!")

            elif sched_status["status"] in ("IN_WINDOW", "ALL_DAY"):
                target_pid = resolve_target_pid()
                if target_pid and not uploader._cached_driver and cycle == 0:
                    self.emit_log(f"⏰ [Trong khung giờ đăng] {sched_status['description']}")
                    uploader.prewarm_profile(target_pid, self._gpm_client)

            cycle += 1
            if cycle > 1:
                self.emit_log(f"🔄 [Vòng quét #{cycle}] Quét liên tục không nghỉ tìm video mới trên {total} kênh...")

            def handle_key_rotate(old_k, new_k):
                self._api_pool.dead_keys.add(old_k)
                self.emit_log(f"⚠ Quota limit trên key [{old_k[:8]}...], xoay sang key [{new_k[:8]}...]...")
                dead_cnt = len(self._api_pool.dead_keys)
                self._eval_js(f"document.getElementById('stat-key-dead').textContent = '({dead_cnt})'")

            def get_channel_assigned_keys(project: str, channel_url: str) -> List[str]:
                proj_map = self._api_pool.channel_map.get(project, {})
                if channel_url in proj_map:
                    return proj_map[channel_url]
                clean_u = channel_url.strip().rstrip("/").lower()
                for k, v in proj_map.items():
                    if k.strip().rstrip("/").lower() == clean_u:
                        return v
                return []

            # Tối ưu 1: Quét song song đa kênh bằng ThreadPoolExecutor (Concurrent Multi-Channel Scanning)
            # NGUYÊN TẮC: Mỗi kênh CHỈ dùng duy nhất các API keys được cấp phát riêng trong Quản lý Key!
            def scan_channel_task(item):
                c_idx, c_url = item
                assigned_k = get_channel_assigned_keys(proj, c_url)
                has_assigned_keys = bool(assigned_k)
                k_mgr = APIKeyManager(api_keys=assigned_k) if has_assigned_keys else None

                def channel_key_rotate(old_k, new_k):
                    self._api_pool.dead_keys.add(old_k)
                    self.emit_log(f"⚠ [Kênh #{c_idx+1}] Quota limit trên key [{old_k[:8]}...], xoay sang key [{new_k[:8]}...] (Trong {len(assigned_k)} keys cấp riêng)...")
                    dead_cnt = len(self._api_pool.dead_keys)
                    self._eval_js(f"document.getElementById('stat-key-dead').textContent = '({dead_cnt})'")

                t0_s = time.perf_counter()
                vids = []
                engine = "Turbo RSS"

                if not has_assigned_keys:
                    # Kênh chưa được chia API trong Quản lý Key -> CHỈ quét qua Turbo RSS (0 Quota)
                    # Tuyệt đối không dùng chung hay lấy trộm API của kênh khác hoặc kho tổng!
                    engine = "Turbo RSS (0 Quota - Kênh chưa cấp API)"
                    vids = yt_api.get_channel_videos_rss(c_url, limit=2)
                else:
                    # Kênh ĐÃ ĐƯỢC chia API riêng: Luân phiên Turbo RSS & API v3 của riêng kênh
                    use_rss = (cycle + c_idx) % 2 == 1
                    if use_rss:
                        engine = "Turbo RSS"
                        vids = yt_api.get_channel_videos_rss(c_url, limit=2)
                        if not vids and k_mgr and k_mgr.get_keys():
                            engine = f"YouTube API v3 ({len(assigned_k)} keys riêng - Đảo lượt)"
                            vids, _ = yt_api.get_channel_videos_v3(
                                channel_url=c_url,
                                limit=2,
                                key_manager=k_mgr,
                                on_key_rotate=channel_key_rotate
                            )
                    else:
                        engine = f"YouTube API v3 ({len(assigned_k)} keys riêng)"
                        vids, err_v3 = yt_api.get_channel_videos_v3(
                            channel_url=c_url,
                            limit=2,
                            key_manager=k_mgr,
                            on_key_rotate=channel_key_rotate
                        )
                        if not vids:
                            engine = "Turbo RSS (Đảo lượt)"
                            vids = yt_api.get_channel_videos_rss(c_url, limit=2)

                if not vids:
                    vids = downloader.get_channel_videos(c_url, limit=2)
                    engine = "yt-dlp Cào dự phòng"

                t_dur = time.perf_counter() - t0_s
                return (c_idx, c_url, vids, t_dur, engine, len(assigned_k))

            if total > 1:
                self.emit_log(f"🚀 [Quét song song] Đang quét đồng thời {total} kênh qua đa luồng (Độc lập API riêng từng kênh)...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(total, 6)) as scan_pool:
                    scan_results = list(scan_pool.map(scan_channel_task, enumerate(channels)))
            else:
                scan_results = [scan_channel_task((0, channels[0]))]

            for idx, ch_url, videos, t_scan, used_engine, assigned_count in scan_results:
                if not self._is_worker_running:
                    break

                # Resolve per-channel settings
                ch_cfg = ch_settings.get(ch_url, {})
                target_pid = ch_cfg.get("profile_id", "")
                quality = ch_cfg.get("quality", "720")
                process_mode = ch_cfg.get("process_mode", "extend_61s")

                if not target_pid:
                    for prof in tt_cfg.get("profiles", []):
                        if ch_url in prof.get("assigned_channels", []):
                            target_pid = prof.get("profile_id", "")
                            break

                key_badge = f"[{assigned_count} API riêng]" if assigned_count > 0 else "[Chưa cấp API - Quét RSS 0 Quota]"
                if videos:
                    self.emit_log(f"✅ [{idx+1}/{total}] [{used_engine}: {t_scan:.2f}s] {key_badge} Tìm thấy {len(videos)} video từ: {ch_url}!")
                else:
                    self.emit_log(f"⚠️ Kênh '{ch_url}' {key_badge} hiện KHÔNG CÓ video công khai nào trên YouTube (0 video). Vui lòng thêm video lên kênh hoặc đổi kênh khác!")
                    continue

                # Kiểm tra nếu là kênh theo dõi (không phải dán link 1 video đơn lẻ)
                is_direct_video = bool(downloader._extract_single_video_id(ch_url))

                # VÒNG QUÉT ĐẦU TIÊN (cycle == 1): Lập mốc Baseline Snapshot toàn bộ video cũ có sẵn trên kênh
                # Tuyệt đối không tải lại video cũ đã có trước khi bật tool!
                if cycle == 1 and not is_direct_video:
                    existing_ids = {v["id"] for v in videos if v.get("id")}
                    if existing_ids:
                        new_ids = existing_ids - processed_videos
                        if new_ids:
                            processed_videos.update(new_ids)
                            self._save_processed_videos(processed_videos)
                    self.emit_log(f"🛡️ [{idx+1}/{total}] Kênh '{ch_url[:40]}...': Đã ghi nhận mốc {len(existing_ids)} video có sẵn trước khi bật tool. Tool đang trực chiến, CHỈ tải & up khi kênh đăng video MỚI!")
                    continue

                # Lọc bỏ các video đã tải/đăng trước đó hoặc video cũ đăng trước thời điểm bật tool
                processed_videos = self._load_processed_videos()
                unprocessed_videos = []
                for v in videos:
                    v_id = v.get("id")
                    if not v_id or v_id in processed_videos:
                        continue
                    # Bỏ qua các video cũ xuất bản trước thời điểm bật tool (theo timestamp published_at / published)
                    if not is_direct_video:
                        pub_str = v.get("published_at") or v.get("published")
                        if pub_str:
                            try:
                                pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                                if pub_dt < worker_start_time:
                                    processed_videos.add(v_id)
                                    continue
                            except Exception:
                                pass
                    unprocessed_videos.append(v)

                if not unprocessed_videos:
                    if videos:
                        self.emit_log(f"ℹ [{idx+1}/{total}] Kênh '{ch_url[:40]}...': Video mới nhất '{videos[0].get('title', '')[:30]}...' đã up trước đó (đã lưu lịch sử). Tiếp tục theo dõi...")
                    continue

                # Kích hoạt pre-warm GPM profile song song khi có video mới cần up (chỉ khi chưa mở sẵn)
                prewarm_thread = None
                if target_pid and not (uploader._cached_driver and uploader._cached_profile_id == target_pid):
                    def prewarm_worker():
                        uploader.prewarm_profile(target_pid, self._gpm_client)
                    prewarm_thread = threading.Thread(target=prewarm_worker, daemon=True)
                    prewarm_thread.start()
                    self.emit_log(f"🚀 [Pre-warm] Đang mở sẵn Profile GPM [{target_pid[:8]}...] trên nền để tải xong up ngay (0s trễ)...")

                for v_idx, v in enumerate(unprocessed_videos):
                    if not self._is_worker_running:
                        break

                    v_id = v.get("id", "vid_01")
                    title = v.get("title", f"Video {v_id}")
                    v_url = v.get("url", f"https://www.youtube.com/watch?v={v_id}")

                    # Đặt tên file theo Title để TikTok tự động điền Description chuẩn 100% (0s trễ)
                    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title).strip()[:100]
                    file_stem = safe_title if safe_title else v_id
                    raw_path = os.path.join(downloads_dir, f"{file_stem}.mp4")
                    render_path = os.path.join(output_dir, f"{file_stem}_tiktok.mp4")

                    # Kích hoạt tải đón đầu ngầm video kế tiếp (nếu danh sách có nhiều video)
                    if v_idx + 1 < len(unprocessed_videos):
                        next_v = unprocessed_videos[v_idx + 1]
                        next_vid = next_v.get("id")
                        next_title = next_v.get("title", f"Video {next_vid}")
                        next_url = next_v.get("url")
                        next_safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', next_title).strip()[:100]
                        next_file_stem = next_safe if next_safe else next_vid
                        next_raw = os.path.join(downloads_dir, f"{next_file_stem}.mp4")
                        if not os.path.exists(next_raw):
                            threading.Thread(
                                target=downloader.download_video,
                                args=(next_url, next_raw, quality),
                                daemon=True
                            ).start()

                    # 2. Bấm giờ tải video YouTube (Kiểm tra nếu file đã được tải ngầm đón đầu)
                    if os.path.exists(raw_path) and os.path.getsize(raw_path) > 1024 * 1024:
                        self.emit_log(f"⚡ [Tải đón đầu 0s] Video '{title}' ({v_id}) đã có sẵn trong bộ đệm (Tải: 0.00s)!")
                        self.emit_queue_item(v_id, title, 50, "Đã có sẵn (0s)")
                        dl_ok = True
                        t_dl = 0.0
                    else:
                        self.emit_queue_item(v_id, title, 20, f"Đang tải {quality}p...")
                        self.emit_log(f"⚡ Đang tải siêu tốc video {quality}p (32 luồng kết nối song song): {title} ({v_id})...")
                        t0_dl = time.perf_counter()
                        dl_ok = downloader.download_video(v_url, raw_path, quality=quality)
                        t_dl = time.perf_counter() - t0_dl

                    if not dl_ok:
                        self.emit_queue_item(v_id, title, 0, "Lỗi tải")
                        continue

                    video_to_upload = raw_path
                    t_proc = 0.0

                    if process_mode == "extend_61s":
                        self.emit_queue_item(v_id, title, 50, "Edit 61s FFmpeg...")
                        self.emit_log(f"✂ Đang edit video đủ 1 phút 1 giây (≥61s) bằng FFmpeg (Chất lượng {quality}p)...")
                        t0_proc = time.perf_counter()
                        proc_ok = processor.edit_video_for_tiktok(
                            input_path=raw_path,
                            output_path=render_path,
                            mode=process_mode,
                            quality=quality
                        )
                        t_proc = time.perf_counter() - t0_proc

                        if not proc_ok:
                            self.emit_queue_item(v_id, title, 0, "Lỗi render")
                            continue
                        video_to_upload = render_path
                    else:
                        # Chế độ Tải up luôn: Tải xong dùng ngay file gốc, KHÔNG GỌI FFMPEG (0s trễ)!
                        self.emit_queue_item(v_id, title, 75, "Up luôn trực tiếp (0s)...")
                        self.emit_log(f"⚡ Chế độ Tải up luôn: Tải xong dùng luôn file gốc up thẳng lên TikTok (Không dùng FFmpeg, 0s trễ)!")

                    # Đợi prewarm nếu chưa xong (thường đã xong trong lúc tải)
                    if prewarm_thread and prewarm_thread.is_alive():
                        self.emit_log(f"⏳ Đang đợi Profile GPM [{target_pid[:8] if target_pid else ''}...] sẵn sàng trang upload...")
                        prewarm_thread.join(timeout=25)

                    self.emit_queue_item(v_id, title, 85, "Đang upload TikTok...")
                    self.emit_log(f"🚀 Đang tải lên TikTok Studio (GPM Profile [{target_pid[:8] if target_pid else 'Chưa gán'}...] đã mở sẵn)...")

                    # 4. Bấm giờ upload TikTok Studio
                    t0_up = time.perf_counter()
                    up_ok, up_sec, up_msg = uploader.upload_video(
                        video_path=video_to_upload,
                        caption=title,
                        auto_post=auto_post_flag,
                        profile_id=target_pid,
                        gpm_client=self._gpm_client
                    )
                    # Tính thời gian up chuẩn xác từ uploader trả về (chốt ngay khi nhấn Post now xong)
                    t_up = up_sec if (up_sec and up_sec > 0) else (time.perf_counter() - t0_up)

                    t_total = t_scan + t_dl + t_proc + t_up
                    self.emit_queue_item(v_id, title, 100, "Hoàn tất")
                    ffmpeg_info = f"FFmpeg: {t_proc:.2f}s" if process_mode == "extend_61s" else "FFmpeg: 0s (Bỏ qua)"
                    self.emit_log(f"✅ <b>Hoàn tất siêu tốc:</b> {title} | ⏱ <b>Tổng: {t_total:.2f}s</b> (Tải: {t_dl:.2f}s | {ffmpeg_info} | GPM: 0s mở sẵn | Up: {t_up:.2f}s)")

                    if up_ok:
                        processed_videos.add(v_id)
                        self._save_processed_videos(processed_videos)
                        self.emit_log(f"💾 Đã lưu ID [{v_id}] vào config/processed_videos.json (Chống đăng trùng).")
                        self.emit_log(f"🔄 Profile GPM [{target_pid[:8] if target_pid else ''}...] đã được chuyển sẵn về trang Upload để đón video tiếp theo (0s trễ)!")

                    # 5. Báo cáo chi tiết từng bước qua Telegram
                    if self._telegram.enabled:
                        gpm_match = next((p for p in self._get_all_gpm_profiles() if p.get("id") == target_pid), None)
                        gpm_name = gpm_match.get("name") if gpm_match else (target_pid[:8] if target_pid else "Chưa gán")
                        mode_text = "Edit 1m01s (≥61s FFmpeg)" if process_mode == "extend_61s" else "Tải up luôn"

                        tele_report = (
                            f"🚀 <b>[TCD REUP TOOL] BÁO CÁO ĐĂNG VIDEO SIÊU TỐC!</b>\n\n"
                            f"🎬 <b>Video:</b> {title}\n"
                            f"📺 <b>Kênh:</b> {ch_url}\n"
                            f"👤 <b>GPM Profile:</b> {gpm_name} ({target_pid[:8] if target_pid else 'N/A'})\n"
                            f"⚙ <b>Chế độ:</b> {quality}p | {mode_text}\n\n"
                            f"⏱ <b>BẢNG THỜI GIAN THỰC HIỆN:</b>\n"
                            f"• 🔍 Quét API v3: <b>{t_scan:.2f}s</b>\n"
                            f"• ⚡ Tải YouTube: <b>{t_dl:.2f}s</b> (Đa luồng tối đa)\n"
                            f"• ✂ Xử lý FFmpeg: <b>{t_proc:.2f}s</b> {'(Bỏ qua - Up trực tiếp)' if process_mode == 'direct' else ''}\n"
                            f"• 🚀 Mở GPM: <b>Đã mở sẵn (0s độ trễ)</b>\n"
                            f"• 🎵 Upload TikTok: <b>{t_up:.2f}s</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚡ <b>TỔNG THỜI GIAN: {t_total:.2f}s</b> ⚡"
                        )
                        self._telegram.send_message(tele_report)

                    # Giãn cách an toàn tối thiểu giữa các video nếu tải lên liên tiếp nhiều video
                    if self._is_worker_running and len(unprocessed_videos) > 1:
                        post_delay = 5
                        self.emit_log(f"⏳ Giãn cách an toàn {post_delay}s trước khi đăng video tiếp theo...")
                        for _ in range(post_delay):
                            if not self._is_worker_running:
                                break
                            time.sleep(1)

            if not self._is_worker_running:
                break

            # Quét liên tục không nghỉ: chuyển ngay sang vòng quét tiếp theo
            self.emit_log(f"🔄 Hoàn tất vòng #{cycle}. Tiếp tục quét tìm video mới ngay lập tức (Chế độ quét liên tục không nghỉ)...")
            time.sleep(1)

        # Dọn dẹp tài nguyên khi dừng worker
        try:
            uploader.close_browser(self._gpm_client)
        except Exception:
            pass

        self._is_worker_running = False
        self._eval_js("window.onAutomationStateChange(false)")
        self.emit_log("⏹ Đã dừng theo dõi tự động hóa theo yêu cầu người dùng.")
