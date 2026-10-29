"""
Cấu hình TikTok Upload theo Dự Án.
High-fidelity implementation of the TikTok & GPMLogin CDP upload config dialog.
Allows binding one GPM Profile to multiple YouTube channels, configuring timeouts,
customizing video render modes (720P Tối Ưu / 360P Eco), caption templates, and hashtags.
"""
import copy
import logging
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QSpinBox,
    QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QScrollArea, QMessageBox,
    QRadioButton, QButtonGroup, QAbstractItemView, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from src.ui.theme import TCD_NAVY_QSS
from src.core.project_manager import ProjectManager
from src.services.gpm_api_client import GPMLocalAPIClient

logger = logging.getLogger(__name__)


RENDER_MODES = [
    "720P Tối Ưu - Dev & Up",
    "360P Eco - Tiết kiệm dung lượng",
    "1080P Full HD - Nét cao",
    "Original - Giữ nguyên gốc"
]

CAPTION_MODES = [
    "1. Giữ nguyên (title video)",
    "2. Thêm Hashtags xu hướng (#fyp #viral)",
    "3. Xóa ký tự đặc biệt & Giữ nguyên",
    "4. Tùy chỉnh tiền tố + Hậu tố"
]


class TikTokProjectConfigDialog(QDialog):
    """
    Dialog matching 'Cấu hình TikTok Upload theo Dự Án':
    - Gán 1 GPM Profile cho nhiều kênh YouTube.
    - Quản lý kênh chưa có GPM Profile.
    - Cấu hình Timeout chờ đăng, thời gian chờ video tiếp.
    - Cấu hình Caption và Hashtags cho dự án.
    """
    def __init__(self, project_manager: ProjectManager, parent=None):
        super().__init__(parent)
        self.pm = project_manager
        self.project_name = self.pm.active_project
        self.setWindowTitle("Cấu hình TikTok Upload theo Dự Án")
        self.setMinimumSize(1050, 720)
        self.setStyleSheet(TCD_NAVY_QSS)

        # Load project data and current channels
        self.pdata = self.pm.load_project(self.project_name)
        self.channels = self.pdata.get("channels", [])
        self.config_data = copy.deepcopy(self.pm.get_tiktok_config(self.project_name))

        # Ensure profiles list exists
        if not self.config_data.get("profiles"):
            self.config_data["profiles"] = [
                {
                    "profile_id": "143b087-6777-412b-8287-069b806425e3",
                    "profile_name": "New profile 015",
                    "render_mode": "720P Tối Ưu - Dev & Up",
                    "wait_mode": "TikTok Studio (nhanh, không chờ)",
                    "assigned_channels": []
                }
            ]

        self.gpm_client = GPMLocalAPIClient()
        self._setup_ui()
        self._refresh_all_views()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(10)

        # 1. Top Banner
        banner = QFrame()
        banner.setStyleSheet("background-color: #172232; border: 1px solid #283B52; border-radius: 8px; padding: 8px;")
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(10, 6, 10, 6)
        b_layout.setSpacing(3)

        b_title = QLabel("<b style='font-size:14px; color:#38BDF8;'>🎵 CẤU HÌNH TIKTOK UPLOAD</b>")
        b_layout.addWidget(b_title)

        b_sub1 = QLabel("<span style='color:#CBD5E1; font-size:11px;'>• Gán GPM Profile: <b>1 GPM Profile = 1 Proxy = 1 Tài khoản TikTok</b></span>")
        b_sub2 = QLabel("<span style='color:#CBD5E1; font-size:11px;'>• <b>Nhiều kênh YouTube có thể cùng dùng chung 1 GPM Profile</b></span>")
        b_sub3 = QLabel("<span style='color:#CBD5E1; font-size:11px;'>• Chế độ chờ áp dụng cho cả Profile (không phải từng kênh)</span>")
        b_layout.addWidget(b_sub1)
        b_layout.addWidget(b_sub2)
        b_layout.addWidget(b_sub3)
        main_layout.addWidget(banner)

        # 2. Cài Đặt Chung Group
        common_group = QGroupBox("⚙️ Cài đặt chung")
        c_layout = QHBoxLayout(common_group)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(14)

        c_layout.addWidget(QLabel("Timeout chờ đăng video (giây):"))
        self._spin_timeout = QSpinBox()
        self._spin_timeout.setRange(10, 3600)
        self._spin_timeout.setValue(self.config_data.get("timeout_upload_sec", 30))
        self._spin_timeout.setFixedWidth(80)
        c_layout.addWidget(self._spin_timeout)

        c_layout.addSpacing(20)
        c_layout.addWidget(QLabel("Thời gian chờ video tiếp (giây):"))
        self._spin_wait_next = QSpinBox()
        self._spin_wait_next.setRange(10, 3600)
        self._spin_wait_next.setValue(self.config_data.get("wait_next_video_sec", 180))
        self._spin_wait_next.setFixedWidth(80)
        c_layout.addWidget(self._spin_wait_next)
        c_layout.addStretch()

        main_layout.addWidget(common_group)

        # 3. Middle Scroll Area containing Profiles & Unassigned Section
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self._scroll_content = QWidget()
        self._content_layout = QVBoxLayout(self._scroll_content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        # Project Pill & Add Profile Button Row
        p_row = QHBoxLayout()
        self._lbl_pill = QLabel(f"📁 {self.project_name} (0 profiles - 0 kênh)")
        self._lbl_pill.setStyleSheet("""
            background-color: #065F46; color: #34D399; font-weight: bold;
            padding: 4px 12px; border-radius: 12px; font-size: 11px;
        """)
        p_row.addWidget(self._lbl_pill)
        p_row.addStretch()

        btn_sync_gpm = QPushButton("🔄 Đồng Bộ Từ GPMLogin (Port 9495)")
        btn_sync_gpm.setStyleSheet("background-color: #0D9488; border: 1px solid #14B8A6; color: #FFFFFF; font-weight: bold;")
        btn_sync_gpm.clicked.connect(self._sync_profiles_from_gpm)
        p_row.addWidget(btn_sync_gpm)

        btn_add_profile = QPushButton("➕ Thêm GPM Profile Mới")
        btn_add_profile.setStyleSheet("background-color: #1E3A8A; border: 1px solid #3B82F6; color: #FFFFFF; font-weight: bold;")
        btn_add_profile.clicked.connect(self._add_new_profile)
        p_row.addWidget(btn_add_profile)
        self._content_layout.addLayout(p_row)

        # Container for Profiles
        self._profiles_container = QVBoxLayout()
        self._profiles_container.setSpacing(10)
        self._content_layout.addLayout(self._profiles_container)

        # Container for Unassigned Channels Warning Box
        self._unassigned_box = QFrame()
        self._unassigned_box.setStyleSheet("""
            QFrame { background-color: #19141E; border: 1px solid #E11D48; border-radius: 8px; }
        """)
        self._unassigned_layout = QVBoxLayout(self._unassigned_box)
        self._unassigned_layout.setContentsMargins(12, 10, 12, 10)
        self._unassigned_layout.setSpacing(8)

        self._lbl_unassigned_title = QLabel("<b style='color:#FB7185; font-size:12px;'>⚠️ Kênh chưa có GPM Profile (0 kênh)</b>")
        self._unassigned_layout.addWidget(self._lbl_unassigned_title)

        self._unassigned_table = QTableWidget(0, 5)
        self._unassigned_table.setHorizontalHeaderLabels([
            "Kênh YouTube", "Gán vào GPM Profile", "GPM Profile ID", "Mode đăng", "Thao tác"
        ])
        self._unassigned_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._unassigned_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._unassigned_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._unassigned_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._unassigned_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._unassigned_table.setAlternatingRowColors(True)
        self._unassigned_table.setShowGrid(False)
        self._unassigned_table.verticalHeader().setDefaultSectionSize(32)
        self._unassigned_table.setFixedHeight(120)
        self._unassigned_layout.addWidget(self._unassigned_table)

        self._content_layout.addWidget(self._unassigned_box)
        scroll.setWidget(self._scroll_content)
        main_layout.addWidget(scroll, 1)

        # 4. Caption & Hashtags Group
        caption_box = QFrame()
        caption_box.setStyleSheet("background-color: #172232; border: 1px solid #4C1D95; border-radius: 8px; padding: 10px;")
        cap_layout = QVBoxLayout(caption_box)
        cap_layout.setContentsMargins(10, 8, 10, 8)
        cap_layout.setSpacing(8)

        cap_title = QLabel(f"<b style='color:#C084FC; font-size:12px;'>📝 Caption, Hashtag cho dự án: {self.project_name}</b>")
        cap_layout.addWidget(cap_title)

        cap_row = QHBoxLayout()
        cap_row.setSpacing(12)

        cap_row.addWidget(QLabel("Caption Mode:"))
        self._combo_caption = QComboBox()
        self._combo_caption.addItems(CAPTION_MODES)
        c_mode = self.config_data.get("caption_mode", CAPTION_MODES[0])
        idx = self._combo_caption.findText(c_mode)
        if idx >= 0:
            self._combo_caption.setCurrentIndex(idx)
        cap_row.addWidget(self._combo_caption)

        cap_row.addWidget(QLabel("Số Hashtag Click:"))
        self._spin_hashtags = QSpinBox()
        self._spin_hashtags.setRange(0, 30)
        self._spin_hashtags.setValue(self.config_data.get("hashtag_count", 0))
        self._spin_hashtags.setFixedWidth(60)
        cap_row.addWidget(self._spin_hashtags)

        lbl_keep = QLabel("<span style='color:#10B981;'>🔘 Mẫu giữ caption:</span> <i>(Tự động lấy video YouTube)</i>")
        lbl_keep.setStyleSheet("font-size:11px;")
        cap_row.addWidget(lbl_keep)
        cap_row.addStretch()

        cap_layout.addLayout(cap_row)
        main_layout.addWidget(caption_box)

        # 5. Bottom Action Buttons
        btn_row = QHBoxLayout()
        btn_save = QPushButton("💾 Lưu tất cả cấu hình")
        btn_save.setObjectName("btn_primary")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #059669; border: 1px solid #10B981;")
        btn_save.clicked.connect(self._save_all_and_close)

        btn_close = QPushButton("❌ Đóng")
        btn_close.setObjectName("btn_stop")
        btn_close.setFixedHeight(38)
        btn_close.setFixedWidth(130)
        btn_close.clicked.connect(self.reject)

        btn_row.addWidget(btn_save, 3)
        btn_row.addWidget(btn_close, 1)
        main_layout.addLayout(btn_row)

    # --- UI Rendering & State Synchronization ---

    def _refresh_all_views(self):
        """Render profile cards and unassigned channels according to current config."""
        # Clear existing profile cards
        while self._profiles_container.count():
            item = self._profiles_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        profiles = self.config_data.get("profiles", [])
        assigned_all = set()
        for p in profiles:
            assigned_all.update(p.get("assigned_channels", []))

        # Update Project Pill
        self._lbl_pill.setText(f"📁 {self.project_name} ({len(profiles)} profile - {len(self.channels)} kênh)")

        # Render each GPM Profile Card
        for prof_idx, prof in enumerate(profiles):
            card = self._create_profile_card(prof_idx, prof)
            self._profiles_container.addWidget(card)

        # Render Unassigned Channels
        unassigned_channels = [ch for ch in self.channels if ch not in assigned_all]
        self._render_unassigned_section(unassigned_channels, profiles)

    def _create_profile_card(self, prof_idx: int, prof: Dict[str, Any]) -> QWidget:
        """Construct the UI card for one GPM Profile."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame#prof_card {
                background-color: #16202E; border: 1px solid #293B52; border-radius: 8px;
            }
        """)
        card.setObjectName("prof_card")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(12, 10, 12, 10)
        c_layout.setSpacing(8)

        # Profile Header Info Row
        hdr_row = QHBoxLayout()
        hdr_title = QLabel(f"<b>📁 GPM Profile: <span style='color:#38BDF8;'>{prof.get('profile_id', '')}</span></b>")
        hdr_row.addWidget(hdr_title)
        hdr_row.addStretch()

        btn_start_gpm = QPushButton("▶ Mở GPM")
        btn_start_gpm.setStyleSheet("background-color: #065F46; border: 1px solid #10B981; font-size: 11px; padding: 2px 8px;")
        btn_start_gpm.clicked.connect(lambda _, pid=prof.get("profile_id", ""): self._test_start_profile(pid))
        hdr_row.addWidget(btn_start_gpm)

        btn_stop_gpm = QPushButton("⏹ Đóng")
        btn_stop_gpm.setStyleSheet("background-color: #1E293B; border: 1px solid #475569; font-size: 11px; padding: 2px 8px;")
        btn_stop_gpm.clicked.connect(lambda _, pid=prof.get("profile_id", ""): self._test_stop_profile(pid))
        hdr_row.addWidget(btn_stop_gpm)

        btn_del_prof = QPushButton("🗑 Xóa Profile")
        btn_del_prof.setStyleSheet("background-color: #7F1D1D; border: 1px solid #EF4444; font-size: 11px; padding: 2px 8px;")
        btn_del_prof.clicked.connect(lambda _, idx=prof_idx: self._delete_profile(idx))
        hdr_row.addWidget(btn_del_prof)
        c_layout.addLayout(hdr_row)

        # Profile Metadata Row
        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("Tên Profile:"))
        name_edit = QLineEdit(prof.get("profile_name", f"Profile_{prof_idx+1}"))
        name_edit.textChanged.connect(lambda text, idx=prof_idx: self._on_prof_name_changed(idx, text))
        meta_row.addWidget(name_edit)

        meta_row.addWidget(QLabel("Profile ID (GPM UUID):"))
        id_edit = QLineEdit(prof.get("profile_id", ""))
        id_edit.textChanged.connect(lambda text, idx=prof_idx: self._on_prof_id_changed(idx, text))
        meta_row.addWidget(id_edit)

        meta_row.addWidget(QLabel("Mode đăng:"))
        combo_render = QComboBox()
        combo_render.addItems(RENDER_MODES)
        r_mode = prof.get("render_mode", RENDER_MODES[0])
        idx = combo_render.findText(r_mode)
        if idx >= 0:
            combo_render.setCurrentIndex(idx)
        combo_render.currentTextChanged.connect(lambda text, idx=prof_idx: self._on_prof_render_changed(idx, text))
        meta_row.addWidget(combo_render)
        c_layout.addLayout(meta_row)

        # Channels assigned to this profile
        sub_lbl = QLabel("<b>📋 Các kênh sử dụng profile này:</b>")
        sub_lbl.setStyleSheet("color:#93C5FD; font-size:11px;")
        c_layout.addWidget(sub_lbl)

        assigned_ch = prof.get("assigned_channels", [])
        table = QTableWidget(len(assigned_ch), 4)
        table.setHorizontalHeaderLabels(["Kênh YouTube", "GPM Profile Name", "GPM Profile ID", "Thao tác"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.setFixedHeight(max(75, min(140, 32 + len(assigned_ch) * 28)))

        for r_idx, ch_url in enumerate(assigned_ch):
            # Column 0: URL
            table.setItem(r_idx, 0, QTableWidgetItem(ch_url))
            # Column 1: Name
            table.setItem(r_idx, 1, QTableWidgetItem(prof.get("profile_name", "")))
            # Column 2: ID
            table.setItem(r_idx, 2, QTableWidgetItem(prof.get("profile_id", "")))
            # Column 3: Remove button
            btn_remove = QPushButton("🗑 Gỡ kênh")
            btn_remove.setStyleSheet("background-color: #334155; font-size: 10px; padding: 2px 6px;")
            btn_remove.clicked.connect(lambda _, p_idx=prof_idx, c_url=ch_url: self._unassign_channel(p_idx, c_url))
            table.setCellWidget(r_idx, 3, btn_remove)

        c_layout.addWidget(table)

        # Wait mode row
        wait_row = QHBoxLayout()
        wait_row.addWidget(QLabel("🔘 Chế độ chờ (áp dụng cho cả profile):"))
        wait_mode = prof.get("wait_mode", "TikTok Studio (nhanh, không chờ)")

        r_fast = QRadioButton("TikTok Studio (nhanh, không chờ)")
        r_fast.setChecked("nhanh" in wait_mode.lower())
        r_fast.toggled.connect(lambda checked, idx=prof_idx: self._on_wait_mode_changed(idx, "TikTok Studio (nhanh, không chờ)") if checked else None)
        wait_row.addWidget(r_fast)

        r_check = QRadioButton("Chờ kiểm duyệt video xong")
        r_check.setChecked("kiểm duyệt" in wait_mode.lower())
        r_check.toggled.connect(lambda checked, idx=prof_idx: self._on_wait_mode_changed(idx, "Chờ kiểm duyệt video xong") if checked else None)
        wait_row.addWidget(r_check)
        wait_row.addStretch()
        c_layout.addLayout(wait_row)

        return card

    def _render_unassigned_section(self, unassigned: List[str], profiles: List[Dict[str, Any]]):
        """Populate the 'Kênh chưa có GPM Profile' table."""
        count = len(unassigned)
        self._lbl_unassigned_title.setText(f"<b style='color:#FB7185; font-size:12px;'>⚠️ Kênh chưa có GPM Profile ({count} kênh)</b>")
        self._unassigned_table.setRowCount(count)

        if count == 0:
            self._unassigned_box.setVisible(False)
            return
        else:
            self._unassigned_box.setVisible(True)

        for r_idx, ch_url in enumerate(unassigned):
            # Col 0: URL
            self._unassigned_table.setItem(r_idx, 0, QTableWidgetItem(ch_url))

            # Col 1: Select Profile Dropdown
            combo_prof = QComboBox()
            for p in profiles:
                combo_prof.addItem(f"{p.get('profile_name', 'Profile')} ({p.get('profile_id', '')[:8]}...)", p.get("profile_id"))
            self._unassigned_table.setCellWidget(r_idx, 1, combo_prof)

            # Col 2: Profile ID preview
            cur_id = combo_prof.currentData() or ""
            id_item = QTableWidgetItem(cur_id)
            self._unassigned_table.setItem(r_idx, 2, id_item)

            # Col 3: Render mode
            combo_render = QComboBox()
            combo_render.addItems(RENDER_MODES)
            self._unassigned_table.setCellWidget(r_idx, 3, combo_render)

            # Col 4: Assign button
            btn_assign = QPushButton("➕ Gán vào Profile")
            btn_assign.setStyleSheet("background-color: #059669; border: 1px solid #10B981; font-weight: bold; font-size: 11px;")
            btn_assign.clicked.connect(lambda _, c_url=ch_url, cb=combo_prof: self._assign_channel_to_profile(c_url, cb.currentData()))
            self._unassigned_table.setCellWidget(r_idx, 4, btn_assign)

    # --- Action Handlers ---

    def _on_prof_name_changed(self, prof_idx: int, text: str):
        if 0 <= prof_idx < len(self.config_data["profiles"]):
            self.config_data["profiles"][prof_idx]["profile_name"] = text.strip()

    def _on_prof_id_changed(self, prof_idx: int, text: str):
        if 0 <= prof_idx < len(self.config_data["profiles"]):
            self.config_data["profiles"][prof_idx]["profile_id"] = text.strip()

    def _on_prof_render_changed(self, prof_idx: int, text: str):
        if 0 <= prof_idx < len(self.config_data["profiles"]):
            self.config_data["profiles"][prof_idx]["render_mode"] = text

    def _on_wait_mode_changed(self, prof_idx: int, mode_str: str):
        if 0 <= prof_idx < len(self.config_data["profiles"]):
            self.config_data["profiles"][prof_idx]["wait_mode"] = mode_str

    def _add_new_profile(self):
        new_idx = len(self.config_data["profiles"]) + 1
        new_prof = {
            "profile_id": f"gpm_profile_{new_idx:03d}",
            "profile_name": f"New profile {new_idx:03d}",
            "render_mode": "720P Tối Ưu - Dev & Up",
            "wait_mode": "TikTok Studio (nhanh, không chờ)",
            "assigned_channels": []
        }
        self.config_data["profiles"].append(new_prof)
        self._refresh_all_views()

    def _delete_profile(self, prof_idx: int):
        if 0 <= prof_idx < len(self.config_data["profiles"]):
            reply = QMessageBox.question(
                self, "Xác Nhận", "Bạn có chắc muốn xóa GPM Profile này? Các kênh đã gán sẽ trở về trạng thái chưa có profile.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.config_data["profiles"].pop(prof_idx)
                self._refresh_all_views()

    def _assign_channel_to_profile(self, channel_url: str, profile_id: str):
        """Binds a YouTube channel to the specified GPM Profile."""
        for prof in self.config_data["profiles"]:
            if prof.get("profile_id") == profile_id:
                if channel_url not in prof.setdefault("assigned_channels", []):
                    prof["assigned_channels"].append(channel_url)
                break
        self._refresh_all_views()

    def _unassign_channel(self, prof_idx: int, channel_url: str):
        """Unbinds a YouTube channel from its GPM Profile."""
        if 0 <= prof_idx < len(self.config_data["profiles"]):
            assigned = self.config_data["profiles"][prof_idx].get("assigned_channels", [])
            if channel_url in assigned:
                assigned.remove(channel_url)
                self._refresh_all_views()

    def _sync_profiles_from_gpm(self):
        """Fetch profiles directly from running GPMLogin local API server."""
        ok, msg = self.gpm_client.check_connection()
        if not ok:
            QMessageBox.warning(
                self, "Chưa Bật GPMLogin",
                f"Không thể kết nối GPMLogin Local API qua cổng {self.gpm_client.port}!\n\n"
                "Vui lòng đảm bảo:\n"
                "1. Ứng dụng GPMLogin đang được bật trên máy tính.\n"
                "2. Cổng Local API mặc định là 9495 (hoặc kiểm tra file http.port)."
            )
            return

        remote_profiles = self.gpm_client.list_profiles(page_size=100)
        if not remote_profiles:
            QMessageBox.information(self, "GPMLogin", "Đã kết nối GPMLogin nhưng chưa tìm thấy profile nào trong app!")
            return

        existing_ids = {p.get("profile_id") for p in self.config_data["profiles"]}
        added = 0
        for rp in remote_profiles:
            r_id = rp.get("id")
            r_name = rp.get("name", "GPM Profile")
            if r_id and r_id not in existing_ids:
                self.config_data["profiles"].append({
                    "profile_id": r_id,
                    "profile_name": r_name,
                    "render_mode": "720P Tối Ưu - Dev & Up",
                    "wait_mode": "TikTok Studio (nhanh, không chờ)",
                    "assigned_channels": []
                })
                existing_ids.add(r_id)
                added += 1

        self._refresh_all_views()
        QMessageBox.information(
            self, "Đồng Bộ Thành Công",
            f"Đã đồng bộ thành công {len(remote_profiles)} profiles từ ứng dụng GPMLogin (Thêm mới: {added})!"
        )

    def _test_start_profile(self, profile_id: str):
        """Launch browser profile via GPMLogin Local API."""
        if not profile_id:
            QMessageBox.warning(self, "Lỗi", "Profile ID trống!")
            return
        ok, data, msg = self.gpm_client.start_profile(profile_id)
        if ok and isinstance(data, dict):
            port = data.get("remote_debugging_port")
            QMessageBox.information(
                self, "Khởi Động Thành Công",
                f"Đã mở profile '{profile_id[:8]}...' thành công trên GPMLogin!\n"
                f"• Cổng Debugging CDP: {port}\n"
                f"• Driver: {data.get('driver_path')}"
            )
        else:
            QMessageBox.warning(self, "Không Thể Khởi Động", f"Lỗi khởi động profile: {msg}")

    def _test_stop_profile(self, profile_id: str):
        """Stop running browser profile via GPMLogin Local API."""
        if not profile_id:
            return
        ok, msg = self.gpm_client.stop_profile(profile_id)
        if ok:
            QMessageBox.information(self, "Đã Đóng", f"Đã đóng profile '{profile_id[:8]}...' thành công!")
        else:
            QMessageBox.warning(self, "Lỗi", f"Không thể đóng profile: {msg}")

    def _save_all_and_close(self):
        # Update common settings
        self.config_data["timeout_upload_sec"] = self._spin_timeout.value()
        self.config_data["wait_next_video_sec"] = self._spin_wait_next.value()
        self.config_data["caption_mode"] = self._combo_caption.currentText()
        self.config_data["hashtag_count"] = self._spin_hashtags.value()

        # Persist to project configuration
        if self.pm.save_tiktok_config(self.config_data, self.project_name):
            total_prof = len(self.config_data.get("profiles", []))
            total_bound = sum(len(p.get("assigned_channels", [])) for p in self.config_data.get("profiles", []))
            QMessageBox.information(
                self, "Thành Công",
                f"Đã lưu toàn bộ cấu hình TikTok Upload cho dự án '{self.project_name}'!\n"
                f"• GPM Profiles: {total_prof}\n"
                f"• Kênh YouTube đã gắn profile: {total_bound}/{len(self.channels)}"
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể lưu cấu hình TikTok vào file dự án!")
