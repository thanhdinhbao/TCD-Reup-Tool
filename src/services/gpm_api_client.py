"""
GPMLogin Local API Client for TCD REUP TOOL.
Implements the official GPMLogin Local API v1 specification:
- Base URL: http://127.0.0.1:9495/api/v1 (or auto-detected from http.port)
- List profiles, search profiles, create profile
- Start profile (returns remote_debugging_port, websocket_debugging_url, driver_path)
- Stop profile (closes running browser instance)
"""
import os
import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class GPMLocalAPIClient:
    """Client for GPMLogin Local REST API (v1)."""

    def __init__(self, port: int = 9495, host: str = "127.0.0.1"):
        self.host = host
        self.port = port
        self.base_url = f"http://{self.host}:{self.port}/api/v1"
        self._auto_detect_port()

    def _auto_detect_port(self):
        """
        Check if GPMLogin wrote its active port to http.port file
        in %LOCALAPPDATA%/GPMLogin or similar directories.
        """
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\GPMLogin\http.port"),
            os.path.expandvars(r"%APPDATA%\GPMLogin\http.port"),
            r"C:\GPMLogin\http.port",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        p_str = f.read().strip()
                        if p_str.isdigit():
                            self.port = int(p_str)
                            self.base_url = f"http://{self.host}:{self.port}/api/v1"
                            logger.info(f"Auto-detected GPMLogin port from {path}: {self.port}")
                            return
                except Exception:
                    pass

    def _request(self, endpoint: str, method: str = "GET", data: Optional[dict] = None, timeout: int = 8) -> Tuple[bool, Any, str]:
        """Send HTTP request to local GPMLogin API."""
        url = f"http://{self.host}:{self.port}/api/v1{endpoint}"
        body_bytes = None
        headers = {
            "User-Agent": "TCD-VIP-PRO/2.5",
            "Accept": "application/json"
        }
        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_text = resp.read().decode("utf-8")
                res_json = json.loads(resp_text)
                success = res_json.get("success", False)
                payload = res_json.get("data")
                msg = res_json.get("message", "OK")
                return success, payload, msg
        except urllib.error.HTTPError as e:
            try:
                err_text = e.read().decode("utf-8")
                err_json = json.loads(err_text)
                return False, None, err_json.get("message", f"HTTP {e.code}")
            except Exception:
                return False, None, f"HTTP Error {e.code}"
        except urllib.error.URLError as e:
            return False, None, f"Không thể kết nối GPMLogin tại {url}: {e.reason}"
        except Exception as e:
            return False, None, f"Lỗi: {str(e)}"

    def check_connection(self) -> Tuple[bool, str]:
        """Test if GPMLogin local server is running and reachable."""
        ok, data, msg = self._request("/profiles?page=1&page_size=1")
        if ok:
            return True, f"Kết nối GPMLogin thành công qua cổng {self.port}."
        return False, f"Chưa bật ứng dụng GPMLogin hoặc sai cổng {self.port}."

    def list_profiles(self, page: int = 1, page_size: int = 100, search: str = "") -> List[Dict[str, Any]]:
        """
        Fetch paginated list of profiles.
        GET /api/v1/profiles?page={page}&page_size={page_size}&search={search}
        """
        query = f"/profiles?page={page}&page_size={page_size}&sort=0"
        if search:
            query += f"&search={urllib.parse.quote(search)}"

        ok, data, msg = self._request(query)
        if ok and isinstance(data, dict):
            return data.get("data", [])
        return []

    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full information of a profile.
        GET /api/v1/profiles/{id}
        """
        ok, data, msg = self._request(f"/profiles/{profile_id}")
        return data if ok else None

    def create_profile(self, name: str, raw_proxy: str = "", browser_type: int = 1) -> Tuple[bool, Optional[str], str]:
        """
        Create a new profile.
        POST /api/v1/profiles/create
        """
        payload = {
            "name": name,
            "raw_proxy": raw_proxy or None,
            "browser_type": browser_type,
            "timezone_base_on_ip": True,
            "is_language_base_on_ip": True
        }
        ok, data, msg = self._request("/profiles/create", method="POST", data=payload)
        if ok and isinstance(data, dict):
            return True, data.get("id"), msg
        return False, None, msg

    def start_profile(
        self,
        profile_id: str,
        remote_debugging_port: int = 0,
        skip_proxy_check: bool = False
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Launch browser for profile.
        GET /api/v1/profiles/start/{id}?remote_debugging_port=...
        Returns:
            (success, data, message)
            data contains:
              - 'profile_id'
              - 'driver_path'
              - 'remote_debugging_port' (e.g. 40444)
              - 'websocket_debugging_url'
        """
        endpoint = f"/profiles/start/{profile_id}?"
        params = []
        if remote_debugging_port > 0:
            params.append(f"remote_debugging_port={remote_debugging_port}")
        if skip_proxy_check:
            params.append("skip_proxy_check=true")
        endpoint += "&".join(params)

        ok, data, msg = self._request(endpoint, timeout=25)
        if ok and isinstance(data, dict):
            return True, data, msg
        return False, None, msg

    def stop_profile(self, profile_id: str) -> Tuple[bool, str]:
        """
        Close running browser for profile.
        GET /api/v1/profiles/stop/{id}
        """
        ok, data, msg = self._request(f"/profiles/stop/{profile_id}")
        return ok, msg

