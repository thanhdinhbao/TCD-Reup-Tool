"""Unit tests for TCD REUP TOOL components."""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.license_verify import (
    get_hwid, get_drive_id, encrypt_str, decrypt_str,
    _save_license_local, _load_license_local
)
from src.services.telegram_notifier import TelegramNotifier
from src.services.video_processor import VideoProcessor, VideoProcessConfig
from src.services.youtube_downloader import YouTubeDownloader, DownloadConfig
from src.services.youtube_api import APIKeyManager, YouTubeAPIClient
from src.core.project_manager import ProjectManager
from src.services.api_pool_manager import APIPoolManager
from src.services.schedule_analyzer import YouTubeScheduleAnalyzer
from src.services.gpm_api_client import GPMLocalAPIClient
from src.web_api import WebBridgeApi


class TestLicenseVerification(unittest.TestCase):
    def test_get_hwid_returns_valid_string(self):
        hwid = get_hwid()
        self.assertIsInstance(hwid, str)
        self.assertGreater(len(hwid), 0)

    def test_get_drive_id_returns_valid_string(self):
        drive_id = get_drive_id()
        self.assertIsInstance(drive_id, str)
        self.assertGreater(len(drive_id), 0)

    def test_encrypt_and_decrypt_license(self):
        test_secret = "TCD_VIP_TEST_KEY_2026"
        encrypted = encrypt_str(test_secret)
        self.assertIsInstance(encrypted, bytes)
        decrypted = decrypt_str(encrypted)
        self.assertEqual(decrypted, test_secret)

    def test_save_and_load_license_local(self):
        test_file = os.path.join(os.path.dirname(__file__), "temp_cache.bin")
        try:
            with patch("src.core.license_verify.LOCAL_LICENSE_FILE", test_file):
                _save_license_local("MY_ACTIVE_KEY")
                loaded = _load_license_local()
                self.assertEqual(loaded, "MY_ACTIVE_KEY")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


class TestTelegramNotifier(unittest.TestCase):
    def test_telegram_notifier_initialization(self):
        notifier = TelegramNotifier(bot_token="123456:ABC-DEF", telegram_chat_ids=["1001", "1002"])
        self.assertEqual(notifier.bot_token, "123456:ABC-DEF")
        self.assertEqual(len(notifier.telegram_chat_ids), 2)
        self.assertTrue(notifier.is_enabled())

    def test_telegram_notifier_disabled(self):
        notifier = TelegramNotifier(bot_token="", telegram_chat_ids=[])
        self.assertFalse(notifier.is_enabled())
        self.assertFalse(notifier.send_alert("Alert"))

    @patch("requests.post")
    def test_send_message_triggers_http(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        notifier = TelegramNotifier(bot_token="123:ABC", telegram_chat_ids=["1001"])
        self.assertTrue(notifier.send_message("Test"))
        self.assertTrue(notifier.send_alert("Alert"))


class TestVideoProcessor(unittest.TestCase):
    def test_build_video_filename(self):
        proc = VideoProcessor(config=VideoProcessConfig())
        fn = proc._build_video_filename("xyz123", "Video Title")
        self.assertIn("Title", fn)
        self.assertTrue(fn.endswith(".mp4"))

    def test_build_ffmpeg_http_opts(self):
        proc = VideoProcessor()
        opts = proc._build_ffmpeg_http_opts()
        self.assertIn("-headers", opts)

    def test_get_video_duration_nonexistent_returns_zero(self):
        proc = VideoProcessor()
        dur = proc.get_video_duration("non_existent_file.mp4")
        self.assertEqual(dur, 0.0)

    @patch.object(VideoProcessor, "_run_ffmpeg", return_value=True)
    @patch.object(VideoProcessor, "get_video_duration", return_value=30.0)
    def test_edit_video_for_tiktok_extend_61s(self, mock_dur, mock_ffmpeg):
        proc = VideoProcessor()
        dummy_in = os.path.join(os.path.dirname(__file__), "dummy_in.mp4")
        dummy_out = os.path.join(os.path.dirname(__file__), "dummy_out.mp4")
        try:
            with open(dummy_in, "w") as f:
                f.write("test")
            ok = proc.edit_video_for_tiktok(dummy_in, dummy_out, mode="extend_61s", quality="720", target_duration=61.2)
            self.assertTrue(ok)
            # Check ffmpeg command args: should have -stream_loop
            called_cmd = mock_ffmpeg.call_args[0][0]
            self.assertIn("-stream_loop", called_cmd)
            self.assertIn("-t", called_cmd)
        finally:
            if os.path.exists(dummy_in):
                os.remove(dummy_in)
            if os.path.exists(dummy_out):
                os.remove(dummy_out)


class TestYouTubeDownloader(unittest.TestCase):
    def test_clean_channel_url(self):
        dl = YouTubeDownloader(DownloadConfig())
        cleaned = dl._clean_channel_url("https://www.youtube.com/@ChannelName/videos")
        self.assertIn("@ChannelName", cleaned)


class TestYouTubeAPI(unittest.TestCase):
    def test_key_manager_rotation(self):
        mgr = APIKeyManager(["KEY_A", "KEY_B"])
        self.assertEqual(mgr.get_current_key(), "KEY_A")
        mgr.rotate()
        self.assertEqual(mgr.get_current_key(), "KEY_B")

    def test_key_manager_persistence(self):
        temp_file = os.path.join(os.path.dirname(__file__), "test_api_keys.json")
        try:
            mgr = APIKeyManager(config_path=temp_file)
            mgr.set_keys(["AIzaSy123", "AIzaSy456"])
            self.assertEqual(len(mgr.get_keys()), 2)
            self.assertTrue(os.path.exists(temp_file))

            # Load into new manager
            mgr2 = APIKeyManager(config_path=temp_file)
            self.assertEqual(mgr2.get_keys(), ["AIzaSy123", "AIzaSy456"])
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    @patch("urllib.request.urlopen")
    def test_youtube_api_client_rotation_on_quota_limit(self, mock_urlopen):
        import urllib.error
        key_mgr = APIKeyManager(["KEY_RATE_LIMITED", "KEY_HEALTHY"])
        client = YouTubeAPIClient(key_manager=key_mgr)

        # First call raises HTTP 403 quotaExceeded
        err_resp = MagicMock()
        err_resp.read.return_value = json.dumps({"error": {"message": "quotaExceeded"}}).encode("utf-8")
        http_err = urllib.error.HTTPError("url", 403, "quotaExceeded", {}, err_resp)

        # Second call: channels?part=contentDetails returns canonical uploads playlist
        channels_resp = MagicMock()
        channels_resp.__enter__.return_value = channels_resp
        channels_resp.read.return_value = json.dumps({
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1zg56avVRndlbPqZn4-bw"}}}]
        }).encode("utf-8")

        # Third call: playlistItems returns video items
        success_resp = MagicMock()
        success_resp.__enter__.return_value = success_resp
        success_resp.read.return_value = json.dumps({
            "items": [
                {
                    "contentDetails": {"videoId": "test_vid_123"},
                    "snippet": {"title": "Test Video Title", "publishedAt": "2026-10-29T00:00:00Z", "channelTitle": "Test Channel"}
                }
            ]
        }).encode("utf-8")

        mock_urlopen.side_effect = [http_err, channels_resp, success_resp]

        rotated_pairs = []
        def on_rotate(old_k, new_k):
            rotated_pairs.append((old_k, new_k))

        videos, err = client.get_channel_videos_v3(
            channel_url="https://www.youtube.com/channel/UC1zg56avVRndlbPqZn4-bw",
            limit=2,
            key_manager=key_mgr,
            on_key_rotate=on_rotate
        )

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["id"], "test_vid_123")
        self.assertIn("KEY_RATE_LIMITED", key_mgr._rate_limited)
        self.assertEqual(len(rotated_pairs), 1)
        self.assertEqual(rotated_pairs[0][0], "KEY_RATE_LIMITED")



class TestProjectManager(unittest.TestCase):
    def test_project_lifecycle(self):
        import shutil
        test_dir = os.path.join(os.path.dirname(__file__), "test_proj_dir")
        try:
            pm = ProjectManager(test_dir)
            self.assertIn("1232", pm.list_projects())
            self.assertTrue(pm.create_project("MyProject_Beta"))
            self.assertIn("MyProject_Beta", pm.list_projects())
            pm.switch_project("MyProject_Beta")
            self.assertEqual(pm.active_project, "MyProject_Beta")
            self.assertTrue(pm.delete_project("MyProject_Beta"))
            self.assertNotIn("MyProject_Beta", pm.list_projects())
        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)

    def test_tiktok_config_and_channel_binding(self):
        import shutil
        test_dir = os.path.join(os.path.dirname(__file__), "test_proj_dir_tt")
        try:
            pm = ProjectManager(test_dir)
            cfg = pm.get_tiktok_config("1232")
            self.assertIn("timeout_upload_sec", cfg)
            self.assertIn("profiles", cfg)

            # Assign 2 channels to 1 GPM profile
            ch1 = "https://youtube.com/channel/UC_test_1"
            ch2 = "https://youtube.com/channel/UC_test_2"
            cfg["profiles"][0]["assigned_channels"] = [ch1, ch2]
            pm.save_tiktok_config(cfg, "1232")

            # Verify binding
            p1 = pm.get_profile_for_channel(ch1, "1232")
            p2 = pm.get_profile_for_channel(ch2, "1232")
            self.assertIsNotNone(p1)
            self.assertIsNotNone(p2)
            self.assertEqual(p1["profile_id"], p2["profile_id"])
        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)


class TestAPIPoolManager(unittest.TestCase):
    def test_pool_distribution_and_recovery(self):
        import shutil
        test_dir = os.path.join(os.path.dirname(__file__), "test_pool_dir")
        os.makedirs(test_dir, exist_ok=True)
        try:
            pool_mgr = APIPoolManager(test_dir)
            sample_keys = [f"KEY_{i:04d}" for i in range(1, 301)]
            pool_mgr.update_pool_keys(sample_keys)
            self.assertEqual(pool_mgr.get_total_count(), 300)
            self.assertEqual(pool_mgr.get_remaining_count(), 300)

            # Test distribution across 2 channels with 100 keys each
            targets = [
                ("Folder_1", "https://youtube.com/@ChannelA", "Proj_1"),
                ("Folder_2", "https://youtube.com/@ChannelB", "Proj_1"),
            ]
            res = pool_mgr.distribute_all(targets, keys_per_channel=100)
            self.assertEqual(res["total_assigned"], 200)
            self.assertEqual(res["remaining_keys"], 100)
            self.assertEqual(pool_mgr.get_remaining_count(), 100)

            # Check duplicates
            self.assertEqual(len(pool_mgr.find_duplicate_keys()), 0)

            # Simulate dead keys and recovery
            pool_mgr.dead_keys.add("KEY_0001")
            pool_mgr.dead_keys.add("KEY_0002")
            recovered, affected = pool_mgr.recover_garbage_keys()
            self.assertGreaterEqual(recovered, 2)
            self.assertEqual(affected, 1)

            # Clean .bak files
            dummy_bak = os.path.join(test_dir, "test.json.bak")
            with open(dummy_bak, "w") as f:
                f.write("bak")
            del_count = pool_mgr.clean_backup_files()
            self.assertGreaterEqual(del_count, 1)
        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)


class TestScheduleAnalyzer(unittest.TestCase):
    def test_cluster_times_multi(self):
        analyzer = YouTubeScheduleAnalyzer()
        # Minutes representing 09:30, 09:45 (cluster 1) and 19:15, 19:30 (cluster 2)
        minutes = [9 * 60 + 30, 9 * 60 + 45, 19 * 60 + 15, 19 * 60 + 30]
        clusters = analyzer._cluster_times_multi(minutes, max_gap_minutes=60)
        self.assertEqual(len(clusters), 2)
        self.assertIn("09:", clusters[0]["start"])
        self.assertIn("19:", clusters[1]["start"])

    def test_cluster_times_single(self):
        analyzer = YouTubeScheduleAnalyzer()
        minutes = [9 * 60 + 30, 19 * 60 + 30]
        clusters = analyzer._cluster_times_single(minutes)
        self.assertEqual(len(clusters), 1)

    def test_analyze_all_time(self):
        analyzer = YouTubeScheduleAnalyzer()
        schedules = analyzer.analyze([], mode="all_time")
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0]["start"], "00:00")
        self.assertEqual(schedules[0]["end"], "23:59")

    def test_get_schedule_status_all_day(self):
        # Empty schedule runs all day
        status = YouTubeScheduleAnalyzer.get_schedule_status([])
        self.assertEqual(status["status"], "ALL_DAY")
        self.assertTrue(status["should_gpm_open"])
        self.assertTrue(status["in_window"])

    def test_get_schedule_status_in_window(self):
        from datetime import datetime
        schedules = [{"start": "11:00", "end": "12:30"}]
        test_dt = datetime(2026, 10, 29, 11, 45)  # Inside 11:00-12:30
        status = YouTubeScheduleAnalyzer.get_schedule_status(schedules, current_dt=test_dt)
        self.assertEqual(status["status"], "IN_WINDOW")
        self.assertTrue(status["should_gpm_open"])
        self.assertTrue(status["in_window"])
        self.assertFalse(status["approaching"])

    def test_get_schedule_status_approaching(self):
        from datetime import datetime
        schedules = [{"start": "11:00", "end": "12:30"}]
        # 10:55 is 5 mins before 11:00 (within prewarm_mins=10)
        test_dt = datetime(2026, 10, 29, 10, 55)
        status = YouTubeScheduleAnalyzer.get_schedule_status(schedules, prewarm_mins=10, current_dt=test_dt)
        self.assertEqual(status["status"], "APPROACHING")
        self.assertTrue(status["should_gpm_open"])
        self.assertFalse(status["in_window"])
        self.assertTrue(status["approaching"])
        self.assertEqual(status["mins_until_next"], 5)

    def test_get_schedule_status_outside(self):
        from datetime import datetime
        schedules = [{"start": "18:00", "end": "19:30"}]
        test_dt = datetime(2026, 10, 29, 14, 0)  # 4 hours before 18:00
        status = YouTubeScheduleAnalyzer.get_schedule_status(schedules, prewarm_mins=10, current_dt=test_dt)
        self.assertEqual(status["status"], "OUTSIDE")
        self.assertFalse(status["should_gpm_open"])
        self.assertFalse(status["in_window"])
        self.assertFalse(status["approaching"])
        self.assertEqual(status["mins_until_next"], 240)

    def test_is_current_time_in_schedule(self):
        # Empty schedule returns True (run 24/7)
        self.assertTrue(YouTubeScheduleAnalyzer.is_current_time_in_schedule([]))
        # 00:00 to 23:59 covers everything
        self.assertTrue(YouTubeScheduleAnalyzer.is_current_time_in_schedule([{"start": "00:00", "end": "23:59"}]))


class TestGPMLocalAPIClient(unittest.TestCase):
    def test_client_init_and_port(self):
        client = GPMLocalAPIClient(port=9495)
        self.assertEqual(client.port, 9495)
        self.assertEqual(client.base_url, "http://127.0.0.1:9495/api/v1")

    @patch("urllib.request.urlopen")
    def test_mock_list_profiles(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "success": True,
            "data": {
                "data": [
                    {"id": "test-uuid-1", "name": "Profile 01"}
                ]
            },
            "message": "OK"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = GPMLocalAPIClient(port=9495)
        profiles = client.list_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["id"], "test-uuid-1")

    @patch("urllib.request.urlopen")
    def test_mock_start_profile(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "success": True,
            "data": {
                "profile_id": "test-uuid-1",
                "remote_debugging_port": 40444,
                "driver_path": "C:\\GPMLogin\\chromedriver.exe"
            },
            "message": "OK"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = GPMLocalAPIClient(port=9495)
        ok, data, msg = client.start_profile("test-uuid-1", skip_proxy_check=True)
        self.assertTrue(ok)
        self.assertEqual(data["remote_debugging_port"], 40444)

        # Kiểm tra request URL chứa đầy đủ addition_args và skip_proxy_check
        req_arg = mock_urlopen.call_args[0][0]
        req_url = req_arg.full_url if hasattr(req_arg, "full_url") else str(req_arg)
        self.assertIn("skip_proxy_check=true", req_url)
        self.assertIn("addition_args=", req_url)
        self.assertIn("remote-allow-origins", req_url)
        self.assertIn("disable-background-timer-throttling", req_url)


class TestWebBridgeApi(unittest.TestCase):
    def setUp(self):
        import shutil
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_web_api_dir")
        os.makedirs(self.test_dir, exist_ok=True)
        self.bridge = WebBridgeApi(base_path=self.test_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_initial_state(self):
        state = self.bridge.get_initial_state()
        self.assertIn("active_project", state)
        self.assertIn("projects", state)
        self.assertIn("channels", state)
        self.assertIn("threads", state)

    def test_create_and_switch_project(self):
        res = self.bridge.create_project("Project_Web_1")
        self.assertTrue(res["success"])
        self.assertIn("Project_Web_1", res["projects"])

        switch_res = self.bridge.switch_project("Project_Web_1")
        self.assertTrue(switch_res["success"])
        self.assertEqual(switch_res["active_project"], "Project_Web_1")

    def test_save_project_state(self):
        self.bridge.create_project("Project_Save_Test")
        success = self.bridge.save_project_state({
            "channels": ["https://youtube.com/@ChannelWeb"],
            "threads": 250,
            "use_proxy": True,
            "proxy_region": "IP - Singapore"
        })
        self.assertTrue(success)

        state = self.bridge.get_initial_state()
        self.assertIn("https://youtube.com/@ChannelWeb", state["channels"])
        self.assertEqual(state["threads"], 250)
        self.assertTrue(state["use_proxy"])

    def test_update_master_pool_and_distribution(self):
        keys = "\n".join([f"API_KEY_{i:04d}" for i in range(1, 151)])
        res = self.bridge.update_master_pool(keys)
        self.assertEqual(res["total"], 150)

        pool_data = self.bridge.get_api_pool_data()
        self.assertEqual(pool_data["total_keys"], 150)

    def test_tiktok_config_saving(self):
        cfg = {
            "upload_timeout": 45,
            "next_video_delay": 200,
            "profiles": [
                {
                    "profile_id": "gpm-123",
                    "profile_name": "Profile 1",
                    "youtube_channels": ["https://youtube.com/@ChannelWeb"]
                }
            ]
        }
        res = self.bridge.save_tiktok_config(cfg)
        self.assertTrue(res)

    def test_clear_processed_history(self):
        # Lưu và làm mới danh sách video đã tải
        self.bridge._save_processed_videos({"vid_01", "vid_02"})
        loaded = self.bridge._load_processed_videos()
        self.assertIn("vid_01", loaded)

        res = self.bridge.clear_processed_history()
        self.assertTrue(res["success"])
        cleared = self.bridge._load_processed_videos()
        self.assertEqual(len(cleared), 0)

    def test_save_project_state_skip_horizontal(self):
        state = {
            "channels": ["https://youtube.com/@NewChannel"],
            "threads": 250,
            "use_proxy": True,
            "proxy_region": "IP - US",
            "auto_upload_tiktok": False,
            "only_shorts": True,
            "skip_horizontal": True
        }
        res = self.bridge.save_project_state(state)
        self.assertTrue(res)
        pstate = self.bridge.get_initial_state()
        self.assertTrue(pstate.get("only_shorts"))
        self.assertTrue(pstate.get("skip_horizontal"))

    def test_is_shorts_and_is_horizontal(self):
        from src.services.youtube_downloader import YouTubeDownloader
        yd = YouTubeDownloader()
        # Direct shorts check
        self.assertTrue(yd.is_shorts("https://www.youtube.com/shorts/tQryjZKQmwc"))
        # Shorts should not be considered horizontal
        self.assertFalse(yd.is_horizontal("https://www.youtube.com/shorts/tQryjZKQmwc"))


if __name__ == "__main__":
    unittest.main()

