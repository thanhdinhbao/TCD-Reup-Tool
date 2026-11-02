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

