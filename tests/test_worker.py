"""Tests for background AutomationWorker and pipeline integration."""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.worker import AutomationWorker
from src.services.video_processor import VideoProcessor
from src.services.tiktok_uploader import TikTokUploader


class TestAutomationWorker(unittest.TestCase):
    def test_worker_initialization(self):
        worker = AutomationWorker(
            channels=["https://www.youtube.com/@Sample"],
            base_path=os.path.dirname(__file__),
            auto_upload_tiktok=False,
            gpm_port="9222"
        )
        self.assertEqual(len(worker.channels), 1)
        self.assertEqual(worker.gpm_port, "9222")
        self.assertTrue(worker._is_running)

    def test_worker_stop(self):
        worker = AutomationWorker(
            channels=[],
            base_path=os.path.dirname(__file__)
        )
        worker.stop()
        self.assertFalse(worker._is_running)

    @patch("src.services.youtube_downloader.YouTubeDownloader.get_channel_videos")
    @patch("src.services.youtube_downloader.YouTubeDownloader.download_video")
    @patch("src.services.video_processor.VideoProcessor.render_for_tiktok")
    def test_worker_run_mocked_pipeline(self, mock_render, mock_dl, mock_videos):
        mock_videos.return_value = [{"id": "vid1", "title": "Test Vid", "url": "http://vid1"}]
        mock_dl.return_value = True
        mock_render.return_value = True

        logs = []
        progresses = []

        worker = AutomationWorker(
            channels=["📺 https://www.youtube.com/@Sample"],
            base_path=os.path.dirname(__file__),
            auto_upload_tiktok=False
        )
        worker.log_signal.connect(lambda msg: logs.append(msg))
        worker.progress_signal.connect(lambda p: progresses.append(p))

        # Test stop immediately after start
        worker.stop()
        worker.run()
        self.assertTrue(any("dừng" in l.lower() or "hoàn thành" in l.lower() for l in logs))


class TestTikTokUploader(unittest.TestCase):
    def test_uploader_init(self):
        uploader = TikTokUploader(remote_debugging_address="127.0.0.1:9222")
        self.assertEqual(uploader.remote_debugging_address, "127.0.0.1:9222")

    @patch("src.services.tiktok_uploader.webdriver.Chrome")
    def test_prewarm_with_gpm_driver_path(self, mock_chrome):
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.tiktok.com/tiktokstudio/upload"
        mock_chrome.return_value = mock_driver

        mock_gpm = MagicMock()
        mock_gpm.start_profile.return_value = (
            True,
            {
                "remote_debugging_port": 60466,
                "driver_path": r"C:\GPMLoginGlobal\Browsers\ChromiumCore_v154\gpmdriver.exe"
            },
            "OK"
        )

        uploader = TikTokUploader()
        ok, msg = uploader.prewarm_profile("prof_123", gpm_client=mock_gpm)
        self.assertTrue(ok)
        self.assertEqual(uploader._cached_driver_path, r"C:\GPMLoginGlobal\Browsers\ChromiumCore_v154\gpmdriver.exe")
        self.assertEqual(uploader.remote_debugging_address, "127.0.0.1:60466")

    def test_click_post_button_by_data_e2e(self):
        uploader = TikTokUploader()
        mock_driver = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_displayed.return_value = True
        mock_btn.get_attribute.side_effect = lambda attr: "false" if attr in ("aria-disabled", "data-disabled", "data-loading") else None

        mock_driver.find_elements.return_value = [mock_btn]

        clicked = uploader.click_post_button(mock_driver, timeout=2)
        self.assertTrue(clicked)
        mock_btn.click.assert_called_once()
        mock_driver.execute_script.assert_any_call("window.scrollTo(0, document.body.scrollHeight);")

    def test_turn_on_and_esc_and_post_now(self):
        uploader = TikTokUploader()
        mock_driver = MagicMock()

        # Mock Turn On button
        mock_turn_on_btn = MagicMock()
        mock_turn_on_btn.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_turn_on_btn]

        clicked_turn_on = uploader.check_and_click_turn_on(mock_driver, timeout=1)
        self.assertTrue(clicked_turn_on)
        mock_turn_on_btn.click.assert_called_once()

        # Mock ESC 3 times
        uploader.press_escape(mock_driver, times=3)
        self.assertEqual(mock_driver.switch_to.active_element.send_keys.call_count, 3)

        # Mock Post Now confirmation
        mock_post_now_btn = MagicMock()
        mock_post_now_btn.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_post_now_btn]

        clicked_post_now = uploader.check_and_click_post_now(mock_driver, timeout=1)
        self.assertTrue(clicked_post_now)
        mock_post_now_btn.click.assert_called_once()

    def test_reset_to_upload_page(self):
        uploader = TikTokUploader()
        mock_driver = MagicMock()
        mock_driver.find_elements.return_value = []
        with patch("time.sleep"):
            ok = uploader.reset_to_upload_page(mock_driver)
            self.assertTrue(ok)
            mock_driver.get.assert_called_with("https://www.tiktok.com/tiktokstudio/upload?from=webapp&tab=video")

    def test_TCD_vip_4_techniques(self):
        from src.services.youtube_downloader import YouTubeDownloader
        from src.services.youtube_api import YouTubeAPIClient

        # 1. Test RSS Feeds parser
        api_client = YouTubeAPIClient()
        xml_sample = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <yt:videoId>TEST_VID_01</yt:videoId>
                <title>Test Video Title</title>
                <published>2026-10-29T00:00:00Z</published>
            </entry>
        </feed>"""
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = xml_sample
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            videos = api_client.get_channel_videos_rss("https://www.youtube.com/channel/UC1234567890abcdef", limit=5)
            self.assertEqual(len(videos), 1)
            self.assertEqual(videos[0]["id"], "TEST_VID_01")
            self.assertEqual(videos[0]["title"], "Test Video Title")

        # 2. Test Range 0-0 Size Extraction
        downloader = YouTubeDownloader()
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.headers = {"Content-Range": "bytes 0-0/41658310"}
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            size = downloader._lay_size_qua_range("http://stream.googlevideo.com/test")
            self.assertEqual(size, 41658310)

        # 3. Test In-place Seek Download
        with patch.object(downloader, "_download_chunk_inplace", return_value=True):
            test_target = os.path.join(os.path.dirname(__file__), "test_dummy_inplace.mp4")
            try:
                ok = downloader._native_range_download("http://stream.url", test_target, filesize=1024 * 1024, num_chunks=4)
                self.assertTrue(ok)
                self.assertEqual(os.path.getsize(test_target), 1024 * 1024)
            finally:
                if os.path.exists(test_target):
                    os.remove(test_target)

        # 4. Test Android Innertube Fast Path
        innertube_sample = json.dumps({
            "streamingData": {
                "formats": [
                    {"itag": 18, "url": "https://googlevideo.com/direct_stream_360p"}
                ]
            }
        }).encode("utf-8")
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = innertube_sample
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            url_found = downloader._get_mobile_innertube_stream("VID_123")
            self.assertEqual(url_found, "https://googlevideo.com/direct_stream_360p")


class TestChannelAPIKeyIsolation(unittest.TestCase):
    def test_key_isolation_between_channels(self):
        """Test that each channel strictly uses only its allocated keys."""
        from src.services.api_pool_manager import APIPoolManager
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            pool = APIPoolManager(base_path=tmp_dir)
            pool.master_pool = ["KEY_A1", "KEY_A2", "KEY_B1", "KEY_B2", "KEY_UNASSIGNED"]
            
            targets = [
                ("Folder_1", "https://youtube.com/@ChannelA", "Project1"),
                ("Folder_2", "https://youtube.com/@ChannelB", "Project1"),
            ]
            
            # Distribute 2 keys per channel
            res = pool.distribute_all(targets, keys_per_channel=2)
            self.assertEqual(res["total_assigned"], 4)
            
            # Channel A must have KEY_A1, KEY_A2
            keys_a = pool.channel_map["Project1"]["https://youtube.com/@ChannelA"]
            self.assertEqual(keys_a, ["KEY_A1", "KEY_A2"])
            
            # Channel B must have KEY_B1, KEY_B2
            keys_b = pool.channel_map["Project1"]["https://youtube.com/@ChannelB"]
            self.assertEqual(keys_b, ["KEY_B1", "KEY_B2"])
            
            # Channel C has NO keys allocated -> empty list, cannot use A or B
            keys_c = pool.channel_map.get("Project1", {}).get("https://youtube.com/@ChannelC", [])
            self.assertEqual(keys_c, [])
            
            # Verify unassigned
            unassigned = pool.get_unassigned_keys()
            self.assertEqual(unassigned, ["KEY_UNASSIGNED"])


if __name__ == "__main__":
    unittest.main()
