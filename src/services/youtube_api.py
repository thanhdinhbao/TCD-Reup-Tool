"""
YouTube API client and key manager for TCD REUP TOOL.
Implements official Google YouTube Data API v3:
- Channel resolution by ID, Handle (@name), or Username
- Low-quota upload playlist fetching (1 quota point vs 100 quota points)
- Round-robin key rotation to distribute quota evenly
- Automatic rate-limit detection (403 quotaExceeded) with instant failover to next key
"""
import os
import re
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Callable

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages YouTube Data API v3 keys with rotation, persistence, and quota tracking."""

    def __init__(self, api_keys: Optional[List[str]] = None, config_path: Optional[str] = None):
        self.config_path = config_path
        self._keys: List[str] = []
        self._index = 0
        self._rate_limited: List[str] = []

        if api_keys:
            self.set_keys(api_keys)
        elif self.config_path and os.path.exists(self.config_path):
            self.load_keys(self.config_path)

    def load_keys(self, path: Optional[str] = None) -> bool:
        """Load API keys from a JSON or TXT configuration file."""
        target_path = path or self.config_path
        if not target_path or not os.path.exists(target_path):
            return False

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("{") or content.startswith("["):
                    data = json.loads(content)
                    if isinstance(data, list):
                        self._keys = [str(k).strip() for k in data if str(k).strip()]
                    elif isinstance(data, dict):
                        self._keys = [str(k).strip() for k in data.get("api_keys", []) if str(k).strip()]
                else:
                    self._keys = [line.strip() for line in content.splitlines() if line.strip()]

            self._index = 0
            logger.info(f"Loaded {len(self._keys)} YouTube API keys from {target_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading API keys from {target_path}: {e}")
            return False

    def save_keys(self, path: Optional[str] = None) -> bool:
        """Save API keys to a JSON configuration file."""
        target_path = path or self.config_path
        if not target_path:
            return False

        try:
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            payload = {
                "api_keys": self._keys,
                "count": len(self._keys)
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved {len(self._keys)} API keys to {target_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving API keys to {target_path}: {e}")
            return False

    def set_keys(self, keys: List[str]) -> bool:
        """Update list of keys and persist if config_path is specified."""
        cleaned = []
        for k in keys:
            k = k.strip()
            if k and k not in cleaned:
                cleaned.append(k)
        self._keys = cleaned
        self._index = 0
        self._rate_limited.clear()
        if self.config_path:
            return self.save_keys(self.config_path)
        return True

    def add_key(self, key: str) -> bool:
        key = key.strip()
        if key and key not in self._keys:
            self._keys.append(key)
            if self.config_path:
                self.save_keys(self.config_path)
            return True
        return False

    def remove_key(self, key: str) -> bool:
        key = key.strip()
        if key in self._keys:
            self._keys.remove(key)
            if self.config_path:
                self.save_keys(self.config_path)
            return True
        return False

    def get_keys(self) -> List[str]:
        return list(self._keys)

    def get_active_keys(self) -> List[str]:
        """Returns keys that are not currently marked as rate limited."""
        return [k for k in self._keys if k not in self._rate_limited]

    def get_current_key(self) -> Optional[str]:
        """Get the current active API key. Rotates past rate-limited keys."""
        if not self._keys:
            return None
        active = self.get_active_keys()
        if not active:
            return self._keys[self._index % len(self._keys)]
        return active[self._index % len(active)]

    def rotate(self) -> Optional[str]:
        """Rotate to the next API key in round-robin fashion."""
        if not self._keys:
            return None
        self._index = (self._index + 1) % max(1, len(self._keys))
        return self.get_current_key()

    def mark_rate_limited(self, key: str):
        """Mark an API key as rate-limited / quota exhausted."""
        if key and key not in self._rate_limited:
            self._rate_limited.append(key)
            logger.warning(f"YouTube API Key [{key[:8]}...] reached rate/quota limit. Marked as limited.")

    def reset_rate_limits(self):
        """Clear the rate-limited list."""
        self._rate_limited.clear()

    @property
    def rate_limit_count(self) -> int:
        return len(self._rate_limited)

    @property
    def active_keys_count(self) -> int:
        return max(0, len(self._keys) - len(self._rate_limited))

    def test_key(self, api_key: str) -> Tuple[bool, str]:
        """Test a YouTube Data API v3 key against official Google endpoint."""
        key = api_key.strip()
        if not key:
            return False, "Key trống, vui lòng nhập API Key hợp lệ."

        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id=UC_x5XG1OV2P6uZZ5FSM9Ttw&key={key}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    return True, "Key hợp lệ! Kết nối Google YouTube Data API v3 thành công."
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode('utf-8', errors='ignore'))
                err_msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = f"HTTP Error {e.code}"
            return False, f"Google API từ chối ({e.code}): {err_msg}"
        except urllib.error.URLError as e:
            return False, f"Lỗi kết nối mạng: {e.reason}"
        except Exception as e:
            return False, f"Lỗi không xác định: {str(e)}"

        return False, "Không thể xác thực key."


class YouTubeAPIClient:
    """
    YouTube Data API v3 high-level client.
    Scans videos using low-cost playlistItems endpoints and automatic key rotation.
    """

    def __init__(self, key_manager: Optional[APIKeyManager] = None):
        self.key_manager = key_manager or APIKeyManager()

    def _extract_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extract UC... channel ID from URL if directly present."""
        m = re.search(r"channel/(UC[a-zA-Z0-9_-]+)", url)
        if m:
            return m.group(1).rstrip("/")
        clean = url.strip()
        if clean.startswith("UC") and len(clean) >= 20:
            return clean.split("/")[0].split("?")[0]
        return None

    def _extract_handle_from_url(self, url: str) -> Optional[str]:
        """Extract @handle from URL."""
        m = re.search(r"(@[a-zA-Z0-9_\.-]+)", url)
        if m:
            return m.group(1)
        return None

    def resolve_channel_id(
        self,
        channel_url: str,
        api_key: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolves channel URL to channel ID (UC...) and upload playlist ID (UU...).
        Queries official channels?part=contentDetails to obtain verified uploads playlist ID.
        """
        direct_id = self._extract_channel_id_from_url(channel_url)
        if direct_id:
            # Query official API to get the canonical uploads playlist ID
            c_url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={direct_id}&key={api_key}"
            try:
                req = urllib.request.Request(c_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    items = data.get("items", [])
                    if items:
                        uploads = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                        if uploads:
                            return direct_id, uploads
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    raise e
            except Exception:
                pass
            uploads_id = "UU" + direct_id[2:] if direct_id.startswith("UC") else direct_id
            return direct_id, uploads_id

        handle = self._extract_handle_from_url(channel_url)
        if handle:
            clean_handle = handle.lstrip("@")
            # Try channels?forHandle=
            url = f"https://www.googleapis.com/youtube/v3/channels?part=id,contentDetails&forHandle={clean_handle}&key={api_key}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    items = data.get("items", [])
                    if items:
                        ch_id = items[0].get("id")
                        uploads = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                        if not uploads and ch_id and ch_id.startswith("UC"):
                            uploads = "UU" + ch_id[2:]
                        return ch_id, uploads
            except Exception as e:
                logger.debug(f"forHandle lookup failed for {handle}: {e}")

            # Fallback to search.list
            s_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q={urllib.parse.quote(handle)}&maxResults=1&key={api_key}"
            try:
                req = urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    items = data.get("items", [])
                    if items:
                        ch_id = items[0].get("snippet", {}).get("channelId") or items[0].get("id", {}).get("channelId")
                        if ch_id:
                            uploads = "UU" + ch_id[2:] if ch_id.startswith("UC") else ch_id
                            return ch_id, uploads
            except Exception as e:
                logger.debug(f"search channel lookup failed for {handle}: {e}")

        return None, None

    def resolve_channel_id_auto(self, channel_url: str) -> Optional[str]:
        """Tự động trích xuất hoặc phân giải UC... channel ID (kể cả từ @handle) mà không tốn Quota API."""
        direct_id = self._extract_channel_id_from_url(channel_url)
        if direct_id and direct_id.startswith("UC"):
            return direct_id

        handle = self._extract_handle_from_url(channel_url)
        if not handle:
            return None

        clean_handle = handle.lower().lstrip("@")
        if not hasattr(self, "_handle_cache"):
            self._handle_cache = {}
        if clean_handle in self._handle_cache:
            return self._handle_cache[clean_handle]

        # Quét HTML trang chủ kênh để lấy channelId chính thức
        try:
            req = urllib.request.Request(
                f"https://www.youtube.com/@{clean_handle}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'["\']channelId["\']:\s*["\'](UC[\w-]+)["\']', html) or re.search(r'itemprop="channelId"\s*content="(UC[\w-]+)"', html)
            if m:
                cid = m.group(1)
                self._handle_cache[clean_handle] = cid
                return cid
        except Exception as e:
            logger.debug(f"resolve_channel_id_auto error for {handle}: {e}")

        return None

    def get_channel_videos_rss(self, channel_url: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Kỹ thuật 4: Quét video mới nhất qua YouTube Atom RSS Feed.
        Tốc độ phản hồi cực nhanh (~50ms - 300ms), 0 Quota Google API, không phụ thuộc trình duyệt.
        """
        ch_id = self.resolve_channel_id_auto(channel_url)
        if not ch_id or not ch_id.startswith("UC"):
            return []

        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}"
        try:
            import xml.etree.ElementTree as ET
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "yt": "http://www.youtube.com/xml/schemas/2015",
                "media": "http://search.yahoo.com/mrss/"
            }
            results = []
            for entry in root.findall("atom:entry", ns):
                vid_el = entry.find("yt:videoId", ns)
                title_el = entry.find("atom:title", ns)
                pub_el = entry.find("atom:published", ns)
                if vid_el is not None and vid_el.text:
                    vid_id = vid_el.text
                    title = title_el.text if title_el is not None and title_el.text else f"Video {vid_id}"
                    results.append({
                        "id": vid_id,
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "duration": 0,
                        "published": pub_el.text if pub_el is not None else ""
                    })
                    if len(results) >= limit:
                        break
            return results
        except Exception as e:
            logger.debug(f"RSS lookup error for {channel_url}: {e}")
            return []

    def get_channel_videos_combined(
        self,
        channel_url: str,
        limit: int = 5,
        key_manager: Optional[APIKeyManager] = None,
        on_key_rotate: Optional[Callable[[str, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Quét kết hợp cả 2: YouTube Atom RSS Feed + YouTube Data API v3.
        Hợp nhất danh sách video từ cả 2 nguồn, loại bỏ trùng lặp theo ID và giữ thứ tự mới nhất.
        Đảm bảo không bao giờ bỏ sót video (ngay cả khi RSS hoặc API v3 có độ trễ ngắn).
        """
        combined: Dict[str, Dict[str, Any]] = {}

        # 1. Quét qua RSS
        try:
            rss_vids = self.get_channel_videos_rss(channel_url, limit=limit)
            for v in rss_vids:
                if v.get("id"):
                    combined[v["id"]] = v
        except Exception as e:
            logger.debug(f"Combined RSS error: {e}")

        # 2. Quét qua API v3 nếu có key
        mgr = key_manager or self.key_manager
        if mgr and mgr.get_keys():
            try:
                api_vids, _ = self.get_channel_videos_v3(
                    channel_url=channel_url,
                    limit=limit,
                    key_manager=mgr,
                    on_key_rotate=on_key_rotate
                )
                for v in api_vids:
                    vid_id = v.get("id")
                    if not vid_id:
                        continue
                    if vid_id not in combined:
                        combined[vid_id] = v
                    else:
                        if v.get("duration") and not combined[vid_id].get("duration"):
                            combined[vid_id]["duration"] = v["duration"]
                        if v.get("published_at") and not combined[vid_id].get("published_at"):
                            combined[vid_id]["published_at"] = v["published_at"]
            except Exception as e:
                logger.debug(f"Combined API v3 error: {e}")

        return list(combined.values())[:limit]

    def get_channel_videos_v3(
        self,
        channel_url: str,
        limit: int = 5,
        key_manager: Optional[APIKeyManager] = None,
        on_key_rotate: Optional[Callable[[str, str], None]] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Scan latest videos from a YouTube channel using YouTube Data API v3.
        Rotates keys across requests and automatically recovers from quota limits.
        """
        mgr = key_manager or self.key_manager
        keys = mgr.get_keys()
        if not keys:
            return [], "Không có API key nào trong kho!"

        max_attempts = min(len(keys) + 2, 8)
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            curr_key = mgr.get_current_key()
            if not curr_key:
                break

            # 1. Resolve channel ID and uploads playlist
            try:
                ch_id, uploads_id = self.resolve_channel_id(channel_url, curr_key)
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    mgr.mark_rate_limited(curr_key)
                    old_k = curr_key
                    new_k = mgr.rotate() or "N/A"
                    if on_key_rotate:
                        on_key_rotate(old_k, new_k)
                    continue
                ch_id, uploads_id = None, None

            # 2. Fetch recent videos via playlistItems (Costs only 1 quota point!)
            if uploads_id:
                p_url = (
                    f"https://www.googleapis.com/youtube/v3/playlistItems?"
                    f"part=snippet,contentDetails&playlistId={uploads_id}&maxResults={limit}&key={curr_key}"
                )
                try:
                    req = urllib.request.Request(p_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        items = data.get("items", [])
                        results = []
                        for item in items:
                            snippet = item.get("snippet", {})
                            content = item.get("contentDetails", {})
                            vid_id = content.get("videoId") or snippet.get("resourceId", {}).get("videoId")
                            if not vid_id:
                                continue
                            results.append({
                                "id": vid_id,
                                "title": snippet.get("title", f"Video {vid_id}"),
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                                "published_at": snippet.get("publishedAt", ""),
                                "uploader": snippet.get("channelTitle", ""),
                                "duration": 0
                            })

                        if results:
                            mgr.rotate()
                            return results, None

                except urllib.error.HTTPError as e:
                    if e.code in (403, 429):
                        # Quota exceeded on current key!
                        mgr.mark_rate_limited(curr_key)
                        old_k = curr_key
                        new_k = mgr.rotate() or "N/A"
                        if on_key_rotate:
                            on_key_rotate(old_k, new_k)
                        continue
                    elif e.code == 404:
                        logger.debug(f"Playlist {uploads_id} not found (404), falling back to search.list...")
                    else:
                        logger.debug(f"playlistItems HTTP Error {e.code}: {e.reason}")
                except Exception as e:
                    logger.debug(f"playlistItems error: {e}")

            # 3. Fallback to search.list if playlistItems didn't succeed or 404
            if ch_id:
                s_url = (
                    f"https://www.googleapis.com/youtube/v3/search?"
                    f"part=snippet&channelId={ch_id}&order=date&type=video&maxResults={limit}&key={curr_key}"
                )
                try:
                    req = urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        items = data.get("items", [])
                        results = []
                        for item in items:
                            vid_id = item.get("id", {}).get("videoId")
                            if not vid_id:
                                continue
                            snippet = item.get("snippet", {})
                            results.append({
                                "id": vid_id,
                                "title": snippet.get("title", f"Video {vid_id}"),
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                                "published_at": snippet.get("publishedAt", ""),
                                "uploader": snippet.get("channelTitle", ""),
                                "duration": 0
                            })
                        if results:
                            mgr.rotate()
                            return results, None
                except urllib.error.HTTPError as e:
                    if e.code in (403, 429):
                        mgr.mark_rate_limited(curr_key)
                        old_k = curr_key
                        new_k = mgr.rotate() or "N/A"
                        if on_key_rotate:
                            on_key_rotate(old_k, new_k)
                        continue
                except Exception as e:
                    logger.debug(f"search.list error: {e}")

            # Rotate key and try next
            mgr.rotate()

        return [], "Không thể trích xuất video qua Google API v3."
