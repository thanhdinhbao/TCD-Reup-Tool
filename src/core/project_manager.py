"""
Project Manager for TCD REUP TOOL.
Handles multiple project workspaces, channel persistence, and configurations.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ProjectManager:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.config_dir = os.path.join(self.base_path, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.projects_dir = os.path.join(self.base_path, "projects")
        self.config_file = os.path.join(self.config_dir, "projects_config.json")
        os.makedirs(self.projects_dir, exist_ok=True)
        self.active_project: str = "1232"
        self._init_defaults()

    def _init_defaults(self):
        """Ensure default project exists."""
        projects = self.list_projects()
        if not projects:
            self.create_project("1232")
            self.active_project = "1232"
        else:
            cfg_path = self.config_file
            if not os.path.exists(cfg_path):
                root_candidate = os.path.join(self.base_path, "projects_config.json")
                if os.path.exists(root_candidate):
                    cfg_path = root_candidate

            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        self.active_project = cfg.get("active_project", projects[0])
                except Exception:
                    self.active_project = projects[0]
            else:
                self.active_project = projects[0]

    def _save_active_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"active_project": self.active_project}, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving active project config: {e}")

    def list_projects(self) -> List[str]:
        """List all available project names."""
        if not os.path.exists(self.projects_dir):
            return []
        files = os.listdir(self.projects_dir)
        names = []
        for f in files:
            if f.endswith(".json"):
                names.append(os.path.splitext(f)[0])
        return sorted(names)

    def get_project_file(self, name: str) -> str:
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip() or "default"
        return os.path.join(self.projects_dir, f"{safe_name}.json")

    def create_project(self, name: str, copy_from: Optional[str] = None) -> bool:
        """Create a new project workspace."""
        name = name.strip()
        if not name:
            return False

        filepath = self.get_project_file(name)
        if os.path.exists(filepath):
            return False

        initial_data = {
            "name": name,
            "channels": [],
            "threads": 500,
            "use_proxy": False,
            "proxy_region": "IP - Nhật Bản",
            "auto_upload_tiktok": True,
            "only_shorts": True,
            "skip_horizontal": True,
            "scan_engine": "both",
            "min_duration": 20,
            "telegram_enabled": True,
            "schedule": [],
            "schedule_mode": "multi",
            "queue": []
        }

        if copy_from:
            existing = self.load_project(copy_from)
            if existing:
                initial_data = existing
                initial_data["name"] = name

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=4, ensure_ascii=False)
            self.active_project = name
            self._save_active_config()
            logger.info(f"Created project: {name}")
            return True
        except Exception as e:
            logger.error(f"Error creating project {name}: {e}")
            return False

    def load_project(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Load project configuration and channels."""
        target = name or self.active_project
        filepath = self.get_project_file(target)
        if not os.path.exists(filepath):
            return {
                "name": target,
                "channels": [],
                "threads": 500,
                "use_proxy": False,
                "proxy_region": "IP - Nhật Bản",
                "auto_upload_tiktok": True,
                "only_shorts": True,
                "skip_horizontal": True,
                "scan_engine": "both",
                "min_duration": 20,
                "telegram_enabled": True,
                "queue": []
            }

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error(f"Error loading project {target}: {e}")
            return {}

    def get_all_projects_details(self) -> List[Dict[str, Any]]:
        """Return list of all projects with channel counts and basic metadata."""
        results = []
        for p_name in self.list_projects():
            pdata = self.load_project(p_name)
            results.append({
                "name": p_name,
                "channel_count": len(pdata.get("channels", [])),
                "is_active": p_name == self.active_project
            })
        return results

    def save_project(self, name: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> bool:
        """Save project state."""
        target = name or self.active_project
        filepath = self.get_project_file(target)
        if data is None:
            return False

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving project {target}: {e}")
            return False

    def delete_project(self, name: str) -> bool:
        """Delete a project."""
        filepath = self.get_project_file(name)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                remaining = self.list_projects()
                if remaining:
                    self.active_project = remaining[0]
                else:
                    self.create_project("1232")
                self._save_active_config()
                return True
            except Exception as e:
                logger.error(f"Error deleting project {name}: {e}")
                return False
        return False

    def switch_project(self, name: str) -> bool:
        """Switch active project."""
        if name in self.list_projects():
            self.active_project = name
            self._save_active_config()
            return True
        return False

    def get_global_tiktok_config(self) -> Dict[str, Any]:
        """
        Lấy cấu hình TikTok Upload toàn cục (áp dụng chung cho tất cả các dự án).
        Mỗi Dự Án gắn liền với 1 Profile GPM. Tất cả các kênh trong 1 dự án ăn theo Profile GPM của dự án đó.
        """
        global_file = os.path.join(self.config_dir, "tiktok_global_config.json")
        default_cfg = {
            "upload_timeout": 30,
            "next_video_delay": 180,
            "gpm_open_mode": "on_new_video",
            "caption_mode": "keep_title",
            "project_configs": {}
        }

        # Nếu file toàn cục đã tồn tại, đọc file
        if os.path.exists(global_file):
            try:
                with open(global_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Đảm bảo đủ các trường cơ bản
                        for k, v in default_cfg.items():
                            if k not in data:
                                data[k] = v
                        # Đảm bảo tất cả các dự án hiện có đều có mục cấu hình
                        p_configs = data.setdefault("project_configs", {})
                        for p_name in self.list_projects():
                            if p_name not in p_configs:
                                p_data = self.load_project(p_name)
                                p_tt = p_data.get("tiktok_config", {})
                                p_ch_cfg = p_tt.get("channels_config", {})
                                first_ch_cfg = next(iter(p_ch_cfg.values())) if p_ch_cfg else {}
                                p_configs[p_name] = {
                                    "profile_id": first_ch_cfg.get("profile_id", ""),
                                    "profile_name": first_ch_cfg.get("profile_name", ""),
                                    "quality": first_ch_cfg.get("quality", "720_fps"),
                                    "fps": first_ch_cfg.get("fps", "120"),
                                    "process_mode": first_ch_cfg.get("process_mode", "direct")
                                }
                        return data
            except Exception as e:
                logger.error(f"Error loading global tiktok config: {e}")

        # Khởi tạo lần đầu từ dữ liệu các dự án hiện có
        all_projs = self.list_projects()
        p_configs = {}
        timeout_val = 30
        delay_val = 180
        gpm_mode = "on_new_video"
        caption_m = "keep_title"

        for p_name in all_projs:
            p_data = self.load_project(p_name)
            p_tt = p_data.get("tiktok_config", {})
            if "upload_timeout" in p_tt:
                timeout_val = p_tt.get("upload_timeout", 30)
            if "next_video_delay" in p_tt:
                delay_val = p_tt.get("next_video_delay", 180)
            if "gpm_open_mode" in p_tt:
                gpm_mode = p_tt.get("gpm_open_mode", "on_new_video")
            if "caption_mode" in p_tt:
                caption_m = p_tt.get("caption_mode", "keep_title")

            p_ch_cfg = p_tt.get("channels_config", {})
            first_ch_cfg = next(iter(p_ch_cfg.values())) if p_ch_cfg else {}
            pid = first_ch_cfg.get("profile_id", "")
            if not pid and p_tt.get("profiles"):
                pid = p_tt["profiles"][0].get("profile_id", "")

            p_configs[p_name] = {
                "profile_id": pid,
                "profile_name": first_ch_cfg.get("profile_name", ""),
                "quality": first_ch_cfg.get("quality", "720_fps"),
                "fps": first_ch_cfg.get("fps", "120"),
                "process_mode": first_ch_cfg.get("process_mode", "direct")
            }

        init_cfg = {
            "upload_timeout": timeout_val,
            "next_video_delay": delay_val,
            "gpm_open_mode": gpm_mode,
            "caption_mode": caption_m,
            "project_configs": p_configs
        }
        try:
            with open(global_file, "w", encoding="utf-8") as f:
                json.dump(init_cfg, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving initial global tiktok config: {e}")

        return init_cfg

    def save_global_tiktok_config(self, config: Dict[str, Any]) -> bool:
        """
        Lưu cấu hình TikTok toàn cục và tự động đồng bộ sang tất cả các file dự án.
        Mỗi kênh YouTube trong từng dự án sẽ tự động ăn theo Profile GPM của dự án đó.
        """
        global_file = os.path.join(self.config_dir, "tiktok_global_config.json")
        try:
            with open(global_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            # Đồng bộ cấu hình sang từng file dự án để đảm bảo tương thích ngược
            p_configs = config.get("project_configs", {})
            for p_name in self.list_projects():
                p_data = self.load_project(p_name)
                p_cfg = p_configs.get(p_name, {})
                tt_sub = p_data.setdefault("tiktok_config", {})

                tt_sub["upload_timeout"] = config.get("upload_timeout", 30)
                tt_sub["next_video_delay"] = config.get("next_video_delay", 180)
                tt_sub["gpm_open_mode"] = config.get("gpm_open_mode", "on_new_video")
                tt_sub["caption_mode"] = config.get("caption_mode", "keep_title")

                # Cập nhật channels_config: mọi kênh của dự án đều gán theo profile của dự án
                channels_map = {}
                for ch in p_data.get("channels", []):
                    channels_map[ch] = {
                        "profile_id": p_cfg.get("profile_id", ""),
                        "quality": p_cfg.get("quality", "720"),
                        "fps": p_cfg.get("fps", "60"),
                        "process_mode": p_cfg.get("process_mode", "extend_61s")
                    }
                tt_sub["channels_config"] = channels_map
                self.save_project(p_name, p_data)

            return True
        except Exception as e:
            logger.error(f"Error saving global tiktok config: {e}")
            return False

    def get_tiktok_config(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Get TikTok upload configuration for the given or active project."""
        pdata = self.load_project(project_name or self.active_project)
        default_cfg = {
            "timeout_upload_sec": 30,
            "wait_next_video_sec": 180,
            "caption_mode": "1. Giữ nguyên (title video)",
            "hashtag_count": 0,
            "profiles": [
                {
                    "profile_id": "143b087-6777-412b-8287-069b806425e3",
                    "profile_name": "New profile 015",
                    "render_mode": "720P Tối Ưu - Dev & Up",
                    "wait_mode": "TikTok Studio (nhanh, không chờ)",
                    "assigned_channels": []
                }
            ]
        }
        return pdata.get("tiktok_config", default_cfg)

    def save_tiktok_config(self, config: Dict[str, Any], project_name: Optional[str] = None) -> bool:
        """Save TikTok upload configuration for project."""
        p_name = project_name or self.active_project
        pdata = self.load_project(p_name)
        pdata["tiktok_config"] = config
        return self.save_project(p_name, pdata)

    def get_profile_for_channel(self, channel_url: str, project_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find the GPM Profile assigned to a specific YouTube channel."""
        cfg = self.get_tiktok_config(project_name)
        for prof in cfg.get("profiles", []):
            if channel_url in prof.get("assigned_channels", []):
                return prof
        return None

