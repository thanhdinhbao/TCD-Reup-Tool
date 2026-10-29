"""
API Pool Manager for TCD REUP TOOL.
Handles master API pool storage, channel distribution logic,
concurrency testing, duplicate detection, garbage key recovery, and backups.
"""
import os
import re
import json
import shutil
import logging
import urllib.request
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Tuple, Optional, Any, Callable

logger = logging.getLogger(__name__)


class APIPoolManager:
    """Core logic engine for managing and distributing YouTube Data API v3 keys."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.config_dir = os.path.join(self.base_path, "config")
        os.makedirs(self.config_dir, exist_ok=True)

        self.pool_file = os.path.join(self.config_dir, "api_pool.json")
        self.mapping_file = os.path.join(self.config_dir, "channel_api_map.json")
        self.history_file = os.path.join(self.config_dir, "api_history.json")

        self.master_pool: List[str] = []
        self.dead_keys: Set[str] = set()
        self.alive_keys: Set[str] = set()
        self.channel_map: Dict[str, Dict[str, List[str]]] = {}  # {project: {channel_url: [keys]}}
        self.last_distribution_time: str = ""

        self.load_data()

    def load_data(self):
        """Load master pool, channel distribution map, and history."""
        # 1. Load Master Pool (with root fallback)
        pool_target = self.pool_file
        if not os.path.exists(pool_target):
            root_candidate = os.path.join(self.base_path, "api_pool.json")
            if os.path.exists(root_candidate):
                pool_target = root_candidate

        if os.path.exists(pool_target):
            try:
                with open(pool_target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.master_pool = [str(k).strip() for k in data if str(k).strip()]
                    elif isinstance(data, dict):
                        self.master_pool = [str(k).strip() for k in data.get("keys", []) if str(k).strip()]
                        self.dead_keys = set(data.get("dead_keys", []))
                        self.alive_keys = set(data.get("alive_keys", []))
            except Exception as e:
                logger.error(f"Error loading master API pool: {e}")
                self.master_pool = []
        else:
            # Check legacy api_keys.json (config or root)
            legacy_file = os.path.join(self.config_dir, "api_keys.json")
            if not os.path.exists(legacy_file):
                legacy_file = os.path.join(self.base_path, "api_keys.json")
            if os.path.exists(legacy_file):
                try:
                    with open(legacy_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        keys = data.get("api_keys", []) if isinstance(data, dict) else data
                        self.master_pool = [str(k).strip() for k in keys if str(k).strip()]
                except Exception:
                    self.master_pool = []

        # 2. Load Mapping (with root fallback)
        map_target = self.mapping_file
        if not os.path.exists(map_target):
            root_candidate = os.path.join(self.base_path, "channel_api_map.json")
            if os.path.exists(root_candidate):
                map_target = root_candidate

        if os.path.exists(map_target):
            try:
                with open(map_target, "r", encoding="utf-8") as f:
                    self.channel_map = json.load(f)
            except Exception as e:
                logger.error(f"Error loading channel API map: {e}")
                self.channel_map = {}

        # 3. Load History (with root fallback)
        hist_target = self.history_file
        if not os.path.exists(hist_target):
            root_candidate = os.path.join(self.base_path, "api_history.json")
            if os.path.exists(root_candidate):
                hist_target = root_candidate

        if os.path.exists(hist_target):
            try:
                with open(hist_target, "r", encoding="utf-8") as f:
                    h = json.load(f)
                    self.last_distribution_time = h.get("last_distribution", "")
            except Exception:
                pass

    def save_pool(self) -> bool:
        """Persist master pool to disk with backup."""
        try:
            self._create_bak(self.pool_file)
            payload = {
                "total": len(self.master_pool),
                "keys": self.master_pool,
                "alive_keys": list(self.alive_keys),
                "dead_keys": list(self.dead_keys),
                "updated_at": datetime.now().isoformat()
            }
            with open(self.pool_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save API pool: {e}")
            return False

    def save_mapping(self) -> bool:
        """Persist channel distribution mapping to disk with backup."""
        try:
            self._create_bak(self.mapping_file)
            with open(self.mapping_file, "w", encoding="utf-8") as f:
                json.dump(self.channel_map, f, indent=4, ensure_ascii=False)
            
            # Save history
            self.last_distribution_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({"last_distribution": self.last_distribution_time}, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to save channel mapping: {e}")
            return False

    def _create_bak(self, file_path: str):
        """Create a timestamped .bak backup file if target exists."""
        if os.path.exists(file_path):
            bak_path = f"{file_path}.bak"
            try:
                shutil.copy2(file_path, bak_path)
            except Exception:
                pass

    # --- Pool Queries & Modifiers ---

    def get_total_count(self) -> int:
        return len(self.master_pool)

    def get_assigned_keys(self) -> Set[str]:
        assigned = set()
        for proj, ch_dict in self.channel_map.items():
            for ch, keys in ch_dict.items():
                assigned.update(keys)
        return assigned

    def get_unassigned_keys(self) -> List[str]:
        assigned = self.get_assigned_keys()
        return [k for k in self.master_pool if k not in assigned]

    def get_remaining_count(self) -> int:
        return len(self.get_unassigned_keys())

    def update_pool_keys(self, new_keys: List[str]) -> Tuple[int, int]:
        """Update the pool from raw text/lines. Returns (total, added_count)."""
        seen = set()
        cleaned = []
        for k in new_keys:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                cleaned.append(k)

        old_set = set(self.master_pool)
        added_count = len([k for k in cleaned if k not in old_set])
        self.master_pool = cleaned
        self.save_pool()
        return len(self.master_pool), added_count

    # --- Distribution Logic ---

    def distribute_all(
        self,
        targets: List[Tuple[str, str, str]],  # (folder_TCD, channel_url, project_name)
        keys_per_channel: int
    ) -> Dict[str, Any]:
        """
        Redistribute keys completely from scratch across all channels.
        Evenly assigns `keys_per_channel` to each channel from the master pool.
        """
        self.channel_map.clear()
        pool_cursor = 0
        total_pool = len(self.master_pool)
        assigned_count = 0
        channels_fully_funded = 0
        channels_partially_funded = 0

        for folder, ch_url, proj in targets:
            if proj not in self.channel_map:
                self.channel_map[proj] = {}

            chunk: List[str] = []
            for _ in range(keys_per_channel):
                if pool_cursor < total_pool:
                    chunk.append(self.master_pool[pool_cursor])
                    pool_cursor += 1
                else:
                    break

            self.channel_map[proj][ch_url] = chunk
            assigned_count += len(chunk)

            if len(chunk) == keys_per_channel:
                channels_fully_funded += 1
            else:
                channels_partially_funded += 1

        self.save_mapping()
        return {
            "total_assigned": assigned_count,
            "remaining_keys": total_pool - pool_cursor,
            "fully_funded": channels_fully_funded,
            "partially_funded": channels_partially_funded
        }

    def distribute_missing_only(
        self,
        targets: List[Tuple[str, str, str]],
        keys_per_channel: int
    ) -> Dict[str, Any]:
        """
        Only distribute to channels that have 0 or fewer than `keys_per_channel` keys.
        Uses currently unassigned keys.
        """
        unassigned = self.get_unassigned_keys()
        cursor = 0
        added_keys = 0

        for folder, ch_url, proj in targets:
            if proj not in self.channel_map:
                self.channel_map[proj] = {}

            current_keys = self.channel_map[proj].get(ch_url, [])
            needed = keys_per_channel - len(current_keys)
            if needed > 0 and cursor < len(unassigned):
                take = min(needed, len(unassigned) - cursor)
                new_chunk = unassigned[cursor:cursor + take]
                cursor += take
                current_keys.extend(new_chunk)
                self.channel_map[proj][ch_url] = current_keys
                added_keys += len(new_chunk)

        self.save_mapping()
        return {
            "added_keys": added_keys,
            "remaining_unassigned": len(unassigned) - cursor
        }

    # --- Garbage Recovery & Duplicate Detection ---

    def recover_garbage_keys(self) -> Tuple[int, int]:
        """
        Removes all dead or invalid keys from channel assignments.
        Returns (recovered_keys_count, affected_channels_count).
        """
        recovered = 0
        affected_channels = 0

        for proj, ch_dict in self.channel_map.items():
            for ch_url, keys in list(ch_dict.items()):
                new_keys = [k for k in keys if k not in self.dead_keys]
                diff = len(keys) - len(new_keys)
                if diff > 0:
                    recovered += diff
                    affected_channels += 1
                    ch_dict[ch_url] = new_keys

        # Also purge dead keys from master pool
        old_pool_len = len(self.master_pool)
        self.master_pool = [k for k in self.master_pool if k not in self.dead_keys]
        purged_from_pool = old_pool_len - len(self.master_pool)

        self.save_mapping()
        self.save_pool()
        return recovered + purged_from_pool, affected_channels

    def find_duplicate_keys(self) -> Dict[str, List[str]]:
        """
        Detects if any API key is assigned to more than one channel.
        Returns {api_key: [channel_list]}.
        """
        key_usage: Dict[str, List[str]] = {}
        for proj, ch_dict in self.channel_map.items():
            for ch_url, keys in ch_dict.items():
                for k in keys:
                    if k not in key_usage:
                        key_usage[k] = []
                    key_usage[k].append(f"[{proj}] {ch_url}")

        duplicates = {k: usages for k, usages in key_usage.items() if len(usages) > 1}
        return duplicates

    def clean_backup_files(self) -> int:
        """Removes all .bak files in the directory. Returns count deleted."""
        count = 0
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                if file.endswith(".bak"):
                    full_p = os.path.join(root, file)
                    try:
                        os.remove(full_p)
                        count += 1
                    except Exception as e:
                        logger.error(f"Cannot remove backup {full_p}: {e}")
        return count

    # --- Live/Dead Testing Engine ---

    @staticmethod
    def test_single_key(key: str) -> Tuple[str, bool, str]:
        """
        Queries YouTube Data API v3 channels endpoint to check if key is valid.
        Returns (key, is_alive, message).
        """
        k = key.strip()
        if not k:
            return key, False, "Key trống"

        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id=UC_x5XG1OV2P6uZZ5FSM9Ttw&key={k}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return key, True, "Sống (200 OK)"
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode('utf-8', errors='ignore'))
                msg = err_data.get("error", {}).get("message", f"HTTP {e.code}")
            except Exception:
                msg = f"HTTP {e.code}"
            return key, False, f"Chết ({e.code}): {msg[:60]}"
        except Exception as e:
            return key, False, f"Lỗi: {str(e)[:50]}"

        return key, False, "Không xác định"
