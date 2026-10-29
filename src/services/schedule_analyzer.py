"""
YouTube Schedule Analyzer for TCD REUP TOOL.
Analyzes historical video upload times across project channels to compute
optimal time windows for running GPMLogin and posting to TikTok.

Features:
- Mode 1: TÁCH CỤM (Khuyên dùng) - clusters upload timestamps < 60 min gap into distinct windows with pre-warm buffers.
- Mode 2: GỘP TẤT CẢ - single continuous window from earliest to latest video upload.
- Intelligent Pre-warm status detection: tells worker when to sleep (OUTSIDE), when to pre-open GPM on TikTok Studio (APPROACHING), and when to scan and post (IN_WINDOW).
"""
import re
import json
import logging
import urllib.request
from datetime import datetime, time, timedelta
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)


class YouTubeScheduleAnalyzer:
    """
    Analyzes video upload timestamps and clusters them into optimal operating schedules.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def _extract_times_from_rss(self, channel_url: str) -> List[datetime]:
        """
        Extract publication dates from YouTube Atom RSS feed.
        0 API quota, response time ~0.2s.
        """
        # Find UC... channel ID if present
        m = re.search(r"channel/(UC[a-zA-Z0-9_-]+)", channel_url)
        ch_id = m.group(1) if m else None
        if not ch_id and channel_url.strip().startswith("UC") and len(channel_url.strip()) >= 20:
            ch_id = channel_url.strip().split("/")[0].split("?")[0]

        if not ch_id:
            return []

        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}"
        timestamps = []
        try:
            import xml.etree.ElementTree as ET
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                root = ET.fromstring(resp.read())
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "yt": "http://www.youtube.com/xml/schemas/2015"
            }
            for entry in root.findall("atom:entry", ns):
                pub_el = entry.find("atom:published", ns)
                if pub_el is not None and pub_el.text:
                    try:
                        dt = datetime.fromisoformat(pub_el.text.replace("Z", "+00:00"))
                        timestamps.append(dt.astimezone())
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"RSS schedule lookup failed for {channel_url}: {e}")

        return timestamps

    def _extract_times_from_api(self, channel_id_or_user: str, max_results: int = 25) -> List[datetime]:
        """Fetch publishedAt timestamps of recent videos via YouTube Data API v3."""
        if not self.api_key:
            return []

        ch_id = channel_id_or_user.strip()
        ch_match = re.search(r"channel/([a-zA-Z0-9_-]+)", ch_id)
        if ch_match:
            ch_id = ch_match.group(1)

        # 1. Try low-quota playlistItems on uploads playlist (UU...)
        if ch_id.startswith("UC"):
            uploads_id = "UU" + ch_id[2:]
            url = (
                f"https://www.googleapis.com/youtube/v3/playlistItems?"
                f"part=snippet&playlistId={uploads_id}&maxResults={max_results}&key={self.api_key}"
            )
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    items = data.get("items", [])
                    timestamps = []
                    for item in items:
                        pub = item.get("snippet", {}).get("publishedAt")
                        if pub:
                            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                            timestamps.append(dt.astimezone())
                    if timestamps:
                        return timestamps
            except Exception as e:
                logger.debug(f"playlistItems lookup failed for {ch_id}: {e}")

        # 2. Fallback to search endpoint
        url = (
            f"https://www.googleapis.com/youtube/v3/search?"
            f"part=snippet&channelId={ch_id}&maxResults={max_results}&order=date&type=video&key={self.api_key}"
        )
        timestamps = []
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data.get("items", []):
                    pub = item.get("snippet", {}).get("publishedAt")
                    if pub:
                        dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                        timestamps.append(dt.astimezone())
        except Exception as e:
            logger.debug(f"search schedule lookup failed for {channel_id_or_user}: {e}")

        return timestamps

    def _extract_times(
        self,
        channel_urls: List[str],
        yt_downloader=None,
        channel_key_map: Optional[Dict[str, List[str]]] = None
    ) -> List[int]:
        """
        Extract upload timestamps from channel list.
        Each channel strictly uses its own assigned API key from channel_key_map if available.
        Returns list of minute-of-day integers (0 - 1439).
        """
        all_minutes: List[int] = []

        for ch in channel_urls:
            # First try Atom RSS (fast & 0 quota)
            times = self._extract_times_from_rss(ch)

            # Then try API key assigned strictly to this channel
            if not times:
                ch_key = None
                if channel_key_map and ch in channel_key_map and channel_key_map[ch]:
                    ch_key = channel_key_map[ch][0]
                elif self.api_key:
                    ch_key = self.api_key

                if ch_key:
                    sub_analyzer = YouTubeScheduleAnalyzer(api_key=ch_key)
                    times = sub_analyzer._extract_times_from_api(ch)

            for dt in times:
                minute_of_day = dt.hour * 60 + dt.minute
                all_minutes.append(minute_of_day)

        # Fallback heuristic if API quota unavailable or no videos found
        if not all_minutes:
            # Common realistic peak upload slots: 11:30 and 19:30
            all_minutes = [11 * 60 + 30, 12 * 60, 19 * 60 + 15, 20 * 60]

        return sorted(all_minutes)

    def _cluster_times_multi(self, minutes: List[int], max_gap_minutes: int = 60) -> List[Dict[str, str]]:
        """
        TÁCH CỤM (Khuyên dùng):
        Clusters timestamps with gap <= `max_gap_minutes` into distinct time windows.
        Creates separate operating windows to save RAM and GPMLogin bandwidth.
        E.g.: Khung 1 (11:00-12:30), Khung 2 (18:00-19:30)...
        """
        if not minutes:
            return []

        clusters: List[List[int]] = []
        current_cluster = [minutes[0]]

        for m in minutes[1:]:
            if m - current_cluster[-1] <= max_gap_minutes:
                current_cluster.append(m)
            else:
                clusters.append(current_cluster)
                current_cluster = [m]
        clusters.append(current_cluster)

        raw_windows: List[Tuple[int, int]] = []
        for cluster in clusters:
            start_m = max(0, min(cluster) - 15)   # 15 min buffer before earliest video
            end_m = min(1439, max(cluster) + 45)  # 45 min buffer after latest video
            raw_windows.append((start_m, end_m))

        # Merge overlapping or touching windows
        merged_windows: List[Tuple[int, int]] = []
        for w in raw_windows:
            if not merged_windows:
                merged_windows.append(w)
            else:
                prev_s, prev_e = merged_windows[-1]
                curr_s, curr_e = w
                if curr_s <= prev_e:
                    # Overlaps or contiguous -> extend
                    merged_windows[-1] = (prev_s, max(prev_e, curr_e))
                else:
                    merged_windows.append(w)

        schedules: List[Dict[str, str]] = []
        for start_m, end_m in merged_windows:
            start_str = f"{start_m // 60:02d}:{start_m % 60:02d}"
            end_str = f"{end_m // 60:02d}:{end_m % 60:02d}"
            schedules.append({"start": start_str, "end": end_str})

        return schedules

    def _cluster_times_single(self, minutes: List[int]) -> List[Dict[str, str]]:
        """
        GỘP TẤT CẢ:
        Combines ALL video timestamps into 1 single broad operating window.
        Runs continuously from earliest upload to latest.
        E.g.: 1 khung 10:00-22:00 (chạy thông suốt cả ngày)
        """
        if not minutes:
            return [{"start": "10:00", "end": "22:00"}]

        start_m = max(0, min(minutes) - 30)
        end_m = min(1439, max(minutes) + 60)

        start_str = f"{start_m // 60:02d}:{start_m % 60:02d}"
        end_str = f"{end_m // 60:02d}:{end_m % 60:02d}"
        return [{"start": start_str, "end": end_str}]

    def analyze(
        self,
        channel_urls: List[str],
        mode: str = "multi",
        channel_key_map: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict[str, str]]:
        """
        Main entry point for schedule analysis.
        mode: 'multi' (Tách cụm) or 'single' (Gộp tất cả)
        channel_key_map: optional mapping {channel_url: [api_keys]} for strict per-channel key isolation.
        """
        minutes = self._extract_times(channel_urls, channel_key_map=channel_key_map)
        if mode == "multi":
            return self._cluster_times_multi(minutes)
        else:
            return self._cluster_times_single(minutes)

    @staticmethod
    def get_schedule_status(
        schedules: List[Dict[str, str]],
        prewarm_mins: int = 10,
        current_dt: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Analyzes the current system time against active schedules and determines:
        - status: 'ALL_DAY' | 'IN_WINDOW' | 'APPROACHING' | 'OUTSIDE'
        - should_gpm_open: True if we are inside a window or approaching within prewarm_mins
        - mins_until_next: minutes until upcoming window start
        - active_window: current window dict or None
        - upcoming_window: next window dict or None
        - description: human-readable Vietnamese status string
        """
        if not schedules:
            return {
                "status": "ALL_DAY",
                "should_gpm_open": True,
                "in_window": True,
                "approaching": False,
                "mins_until_next": 0,
                "active_window": None,
                "upcoming_window": None,
                "description": "Chạy tự do 24/7 (Không giới hạn lịch)"
            }

        now = (current_dt or datetime.now()).time()
        now_m = now.hour * 60 + now.minute

        active_win = None
        upcoming_win = None
        min_diff = 1440 * 2  # large initial sentinel

        for item in schedules:
            try:
                sh, sm = map(int, item["start"].split(":"))
                eh, em = map(int, item["end"].split(":"))
                start_m = sh * 60 + sm
                end_m = eh * 60 + em

                # Check if currently inside window
                is_inside = False
                if start_m <= end_m:
                    is_inside = (start_m <= now_m <= end_m)
                else:  # Crosses midnight (e.g. 23:00 to 02:00)
                    is_inside = (now_m >= start_m or now_m <= end_m)

                if is_inside:
                    active_win = item
                    break

                # Calculate minutes until start of this window
                if now_m <= start_m:
                    diff = start_m - now_m
                else:
                    diff = (1440 - now_m) + start_m

                if diff < min_diff:
                    min_diff = diff
                    upcoming_win = item

            except Exception:
                continue

        if active_win:
            return {
                "status": "IN_WINDOW",
                "should_gpm_open": True,
                "in_window": True,
                "approaching": False,
                "mins_until_next": 0,
                "active_window": active_win,
                "upcoming_window": None,
                "description": f"Đang trong khung giờ đăng [{active_win['start']} - {active_win['end']}]"
            }

        if upcoming_win and 0 < min_diff <= prewarm_mins:
            return {
                "status": "APPROACHING",
                "should_gpm_open": True,
                "in_window": False,
                "approaching": True,
                "mins_until_next": min_diff,
                "active_window": None,
                "upcoming_window": upcoming_win,
                "description": (
                    f"Sắp đến khung giờ đăng [{upcoming_win['start']} - {upcoming_win['end']}] "
                    f"(còn {min_diff} phút). Đang mở sẵn GPM Profile để chờ video..."
                )
            }

        # Outside any window
        next_str = f"[{upcoming_win['start']} - {upcoming_win['end']}]" if upcoming_win else "N/A"
        return {
            "status": "OUTSIDE",
            "should_gpm_open": False,
            "in_window": False,
            "approaching": False,
            "mins_until_next": min_diff if upcoming_win else 0,
            "active_window": None,
            "upcoming_window": upcoming_win,
            "description": (
                f"Ngoài khung giờ đăng. GPM Profile đóng để tiết kiệm tài nguyên. "
                f"Khung kế tiếp: {next_str} (còn {min_diff} phút)."
            )
        }

    @staticmethod
    def is_current_time_in_schedule(schedules: List[Dict[str, str]]) -> bool:
        """Check if current system wall-clock time falls inside any scheduled window."""
        res = YouTubeScheduleAnalyzer.get_schedule_status(schedules)
        return res["in_window"]
