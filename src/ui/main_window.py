"""
Main Window UI for TCD REUP TOOL - YouTube to TikTok Automation Engine.
Pixel-faithful reproduction of the commercial TCD REUP TOOL interface.
Supports multi-project management, rotating YouTube Data API v3 keys,
proxy networking, anti-detect GPMLogin integration, and real-time logs.
"""
import os
import re
import sys
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QListWidget, QTextEdit,
    QProgressBar, QCheckBox, QGroupBox, QSplitter, QStatusBar,
    QDialog, QMessageBox, QFrame, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QSpinBox,
    QRadioButton, QAbstractItemView, QToolTip
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor

from src.ui.theme import TCD_NAVY_QSS
from src.core.project_manager import ProjectManager
from src.services.telegram_notifier import TelegramNotifier
from src.services.youtube_api import APIKeyManager
from src.core.worker import AutomationWorker

logger = logging.getLogger(__name__)


class CreateProjectDialog(QDialog):
    """Popup modal dialog matching the screenshot: 'Tạo dự án mới'."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tạo dự án mới")
        self.setFixedSize(360, 160)
        self.setStyleSheet(TCD_NAVY_QSS)
        self.project_name = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl = QLabel("Nhập tên dự án:")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #CBD5E1;")
        layout.addWidget(lbl)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ví dụ: Dự án 1232, Kênh Review, Tin Tức...")
        self._input.setStyleSheet("font-size: 13px; padding: 7px;")
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.setFixedWidth(80)
        btn_ok.setObjectName("btn_primary")
        btn_ok.clicked.connect(self._on_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedWidth(80)
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _on_ok(self):
        val = self._input.text().strip()
        if not val:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên dự án!")
            return
        self.project_name = val
        self.accept()


class ManageProjectsDialog(QDialog):
    """
    Dialog matching authentic TCD REUP TOOL Project Manager:
    - Lists all projects
    - Displays selected project info (Channels count, Active Schedule)
    - Schedule Manager button
    - Automatic Schedule Analyzer button (Tách cụm / Gộp tất cả)
    - Delete and Switch buttons
    """
    def __init__(self, project_manager: ProjectManager, api_key: str = "", parent=None):
        super().__init__(parent)
        self.pm = project_manager
        self.api_key = api_key
        self.setWindowTitle("Quản lý dự án")
        self.setFixedSize(480, 470)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._selected_proj = self.pm.active_project
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        lbl_list = QLabel("<b>Danh sách dự án:</b>")
        lbl_list.setStyleSheet("color: #E2E8F0; font-size: 13px;")
        layout.addWidget(lbl_list)

        self._list = QListWidget()
        self._list.setFixedHeight(130)
        self._list.setStyleSheet("""
            QListWidget { background-color: #111823; border: 1px solid #283B52; border-radius: 6px; padding: 4px; }
            QListWidget::item { padding: 6px; border-radius: 4px; color: #E2E8F0; }
            QListWidget::item:selected { background-color: #065F46; color: #34D399; font-weight: bold; }
        """)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list)

        # Info Frame
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #172232; border: 1px solid #283B52; border-radius: 8px; padding: 10px;")
        i_layout = QVBoxLayout(info_frame)
        i_layout.setContentsMargins(10, 8, 10, 8)
        i_layout.setSpacing(4)

        title_info = QLabel("<b>Thông tin dự án:</b>")
        title_info.setStyleSheet("color: #93C5FD; font-size: 12px;")
        i_layout.addWidget(title_info)

        self._lbl_name = QLabel("Dự án: --")
        self._lbl_name.setStyleSheet("color: #E2E8F0; font-size: 12px;")
        i_layout.addWidget(self._lbl_name)

        self._lbl_channels = QLabel("Số kênh: 0")
        self._lbl_channels.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        i_layout.addWidget(self._lbl_channels)

        self._lbl_sched = QLabel("Lịch tự động:")
        self._lbl_sched.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        i_layout.addWidget(self._lbl_sched)

        layout.addWidget(info_frame)

        # Schedule Action Buttons
        btn_sched_manage = QPushButton("Quản lý lịch")
        btn_sched_manage.clicked.connect(self._open_schedule_manager)
        layout.addWidget(btn_sched_manage)

        btn_sched_analyze = QPushButton("📊 Phân tích lịch tự động")
        btn_sched_analyze.setStyleSheet("background-color: #1E3A8A; border: 1px solid #3B82F6; color: #FFFFFF; font-weight: bold;")
        btn_sched_analyze.clicked.connect(self._run_schedule_analysis)
        layout.addWidget(btn_sched_analyze)

        self._lbl_sched_status = QLabel("Chưa có lịch nào")
        self._lbl_sched_status.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self._lbl_sched_status)

        # Bottom Buttons Row
        btn_row = QHBoxLayout()
        btn_delete = QPushButton("Xóa dự án")
        btn_delete.setObjectName("btn_stop")
        btn_delete.setFixedWidth(110)
        btn_delete.clicked.connect(self._on_delete)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedWidth(110)
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._populate_list()
        self._update_selected_info()

    def _populate_list(self):
        self._list.clear()
        projects = self.pm.list_projects()
        selected_row = 0
        for idx, p in enumerate(projects):
            self._list.addItem(p)
            if p == self._selected_proj:
                selected_row = idx
        if projects:
            self._list.setCurrentRow(selected_row)

    def _on_item_clicked(self, item):
        self._selected_proj = item.text().strip()
        self.pm.switch_project(self._selected_proj)
        self._update_selected_info()

    def _on_item_double_clicked(self, item):
        self._selected_proj = item.text().strip()
        self.pm.switch_project(self._selected_proj)
        self.accept()

    def _update_selected_info(self):
        if not self._selected_proj:
            return
        pdata = self.pm.load_project(self._selected_proj)
        channels = pdata.get("channels", [])
        schedule = pdata.get("schedule", [])

        self._lbl_name.setText(f"Dự án: <b>{self._selected_proj}</b>")
        self._lbl_channels.setText(f"Số kênh: <b>{len(channels)}</b>")

        if schedule:
            slots_str = ", ".join(f"{s['start']}-{s['end']}" for s in schedule)
            self._lbl_sched.setText(f"Lịch tự động: <b>{len(schedule)} khung ({slots_str})</b>")
            self._lbl_sched_status.setText(f"✅ Đã nạp lịch tự động: {slots_str}")
            self._lbl_sched_status.setStyleSheet("color: #10B981; font-size: 11px;")
        else:
            self._lbl_sched.setText("Lịch tự động: <i>Chưa thiết lập (Chạy 24/7)</i>")
            self._lbl_sched_status.setText("Chưa có lịch nào")
            self._lbl_sched_status.setStyleSheet("color: #94A3B8; font-size: 11px;")

    def _open_schedule_manager(self):
        if not self._selected_proj:
            return
        from src.ui.schedule_dialogs import ScheduleManagerDialog
        pdata = self.pm.load_project(self._selected_proj)
        current_sched = pdata.get("schedule", [])

        dlg = ScheduleManagerDialog(self._selected_proj, current_sched, self)
        if dlg.exec_() == QDialog.Accepted:
            pdata["schedule"] = dlg.schedules
            self.pm.save_project(self._selected_proj, pdata)
            self._update_selected_info()

    def _run_schedule_analysis(self):
        if not self._selected_proj:
            return
        from src.ui.schedule_dialogs import ScheduleModeDialog
        from src.services.schedule_analyzer import YouTubeScheduleAnalyzer

        pdata = self.pm.load_project(self._selected_proj)
        channels = pdata.get("channels", [])

        dlg = ScheduleModeDialog(self._selected_proj, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        mode = dlg.selected_mode
        analyzer = YouTubeScheduleAnalyzer(api_key=self.api_key)
        computed_schedules = analyzer.analyze(channels, mode=mode)

        pdata["schedule"] = computed_schedules
        pdata["schedule_mode"] = mode
        self.pm.save_project(self._selected_proj, pdata)

        self._update_selected_info()

        slots_str = ", ".join(f"{s['start']}-{s['end']}" for s in computed_schedules)
        mode_name = "TÁCH CỤM (< 60p)" if mode == "multi" else "GỘP TẤT CẢ"
        QMessageBox.information(
            self, "Phân Tích Thành Công",
            f"Đã phân tích lịch đăng video theo chế độ [{mode_name}]:\n\n"
            f"• Số khung giờ hoạt động: {len(computed_schedules)}\n"
            f"• Lịch chạy GPM: {slots_str}\n\n"
            f"Hệ thống sẽ chỉ tự động mở GPMLogin và tải video lên TikTok trong các khung giờ này để tiết kiệm RAM & CPU!"
        )

    def _on_delete(self):
        if not self._selected_proj:
            return
        reply = QMessageBox.question(
            self, "Xác nhận", f"Bạn có chắc muốn xóa dự án '{self._selected_proj}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.pm.delete_project(self._selected_proj)
            self._selected_proj = self.pm.active_project
            self._populate_list()
            self._update_selected_info()


class APIKeyManagerDialog(QDialog):
    """Full YouTube Data API v3 configuration dialog."""
    def __init__(self, key_manager: APIKeyManager, parent=None):
        super().__init__(parent)
        self.key_manager = key_manager
        self.setWindowTitle("Quản Lý YouTube Data API v3 Keys")
        self.setMinimumSize(560, 480)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel("<b style='font-size:16px; color:#38BDF8;'>🔑 CẤU HÌNH YOUTUBE DATA API V3</b>")
        layout.addWidget(header)

        desc = QLabel(
            "Nhập danh sách <b>YouTube API Key</b> của bạn vào ô bên dưới (mỗi key nằm trên 1 dòng).<br>"
            "Hệ thống sẽ <b>tự động xoay tua (rotate)</b> giữa các key khi quét video để tránh rate-limit."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#94A3B8; font-size:12px; line-height: 1.4;")
        layout.addWidget(desc)

        self._keys_edit = QTextEdit()
        self._keys_edit.setPlaceholderText(
            "Dán các YouTube API Key tại đây, mỗi key trên 1 dòng:\n\n"
            "AIzaSyD-exampleKey1234567890\n"
            "AIzaSyA-anotherKey0987654321"
        )
        existing_keys = self.key_manager.get_keys()
        if existing_keys:
            self._keys_edit.setPlainText("\n".join(existing_keys))
        layout.addWidget(self._keys_edit)

        self._status_lbl = QLabel(f"Hiện có: <b>{len(existing_keys)}</b> API key được cấu hình.")
        self._status_lbl.setStyleSheet("color:#38BDF8; font-size:12px;")
        layout.addWidget(self._status_lbl)

        btn_row = QHBoxLayout()
        btn_test = QPushButton("🧪 Kiểm Tra Key")
        btn_test.clicked.connect(self._test_current_keys)
        btn_clear = QPushButton("🧹 Xóa Trắng")
        btn_clear.clicked.connect(lambda: self._keys_edit.clear())
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("💾 Lưu & Áp Dụng")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save_keys)

        btn_row.addWidget(btn_test)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        guide_box = QFrame()
        guide_box.setStyleSheet("background-color: #111823; border: 1px dashed #2A3B52; border-radius: 6px; padding: 10px;")
        gb_layout = QVBoxLayout(guide_box)
        gb_layout.setSpacing(4)
        g_title = QLabel("💡 <b>Cách lấy YouTube Data API v3 Key miễn phí:</b>")
        g_title.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        g_desc = QLabel(
            "1. Truy cập <b>console.cloud.google.com</b> và tạo dự án mới.<br>"
            "2. Vào <i>APIs & Services</i> ➜ <i>Library</i> ➜ Tìm và bật <b>YouTube Data API v3</b>.<br>"
            "3. Vào <i>Credentials</i> ➜ Chọn <b>Create Credentials</b> ➜ <b>API Key</b>.<br>"
            "4. Dán key vào đây để tối ưu hóa hạn mức quét video."
        )
        g_desc.setStyleSheet("color: #94A3B8; font-size: 11px;")
        gb_layout.addWidget(g_title)
        gb_layout.addWidget(g_desc)
        layout.addWidget(guide_box)

    def _get_input_keys(self) -> List[str]:
        raw = self._keys_edit.toPlainText().strip()
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _test_current_keys(self):
        keys = self._get_input_keys()
        if not keys:
            QMessageBox.warning(self, "Chưa Nhập Key", "Vui lòng nhập ít nhất một API Key!")
            return

        self._status_lbl.setText("⏳ Đang kiểm tra kết nối tới Google YouTube API...")
        first_key = keys[0]
        ok, msg = self.key_manager.test_key(first_key)
        if ok:
            QMessageBox.information(self, "Kiểm Tra Thành Công", f"Key ({first_key[:12]}...): {msg}")
            self._status_lbl.setText(f"✅ Key hợp lệ! Đang có {len(keys)} key trong danh sách.")
        else:
            QMessageBox.critical(self, "Kiểm Tra Thất Bại", f"Key ({first_key[:12]}...):\n{msg}")
            self._status_lbl.setText(f"❌ Key lỗi: {msg[:60]}")

    def _save_keys(self):
        keys = self._get_input_keys()
        self.key_manager.set_keys(keys)
        self.accept()


class TikTokConfigDialog(QDialog):
    """TikTok and GPMLogin connection settings."""
    def __init__(self, gpm_port="9222", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cấu Hình GPMLogin & TikTok Studio")
        self.setFixedSize(460, 320)
        self.setStyleSheet(TCD_NAVY_QSS)
        self.gpm_port = gpm_port
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("<b style='font-size:15px; color:#38BDF8;'>🚀 CẤU HÌNH GPMLOGIN CHỐNG PHÁT HIỆN</b>")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Cổng CDP (GPM Port):"), 0, 0)
        self._port_input = QLineEdit(self.gpm_port)
        grid.addWidget(self._port_input, 0, 1)

        grid.addWidget(QLabel("Profile ID / Name:"), 1, 0)
        self._profile_input = QLineEdit("TikTok_Channel_01")
        grid.addWidget(self._profile_input, 1, 1)

        grid.addWidget(QLabel("Hashtags mặc định:"), 2, 0)
        self._tags_input = QLineEdit("#fyp #viral #trending #reup")
        grid.addWidget(self._tags_input, 2, 1)

        grid.addWidget(QLabel("Độ trễ đăng (giây):"), 3, 0)
        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(10, 3600)
        self._delay_spin.setValue(120)
        grid.addWidget(self._delay_spin, 3, 1)

        layout.addLayout(grid)

        hint = QLabel("💡 <i>GPMLogin sẽ chạy ngầm qua Chromium CDP giúp vượt qua Cloudflare & bot check.</i>")
        hint.setStyleSheet("color:#64748B; font-size:11px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("💾 Lưu Cấu Hình")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _save(self):
        self.gpm_port = self._port_input.text().strip() or "9222"
        self.accept()


class TelegramConfigDialog(QDialog):
    """Telegram configuration dialog."""
    def __init__(self, notifier: TelegramNotifier, config_path: str, parent=None):
        super().__init__(parent)
        self.notifier = notifier
        self.config_path = config_path
        self.setWindowTitle("Liên Kết Telegram Bot API")
        self.setFixedSize(500, 300)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel("<b style='font-size:15px; color:#38BDF8;'>📢 THIẾT LẬP KẾT NỐI TELEGRAM BOT</b>")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Bot Token:"), 0, 0)
        self._token_input = QLineEdit(self.notifier.bot_token)
        self._token_input.setPlaceholderText("123456789:AAFxAbcDeFgHiJkLmNoPqRsTuVwXyZ...")
        grid.addWidget(self._token_input, 0, 1)

        grid.addWidget(QLabel("Chat IDs:"), 1, 0)
        self._chat_input = QLineEdit(", ".join(self.notifier.telegram_chat_ids))
        self._chat_input.setPlaceholderText("987654321, -100123456789")
        grid.addWidget(self._chat_input, 1, 1)

        layout.addLayout(grid)

        hint = QLabel("💡 <i>Lấy Token từ @BotFather và Chat ID từ bot @userinfobot trên Telegram.</i>")
        hint.setStyleSheet("color:#64748B; font-size:11px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_test = QPushButton("✈ Test Bot")
        btn_test.clicked.connect(self._test)
        btn_save = QPushButton("💾 Lưu")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save)

        btn_row.addWidget(btn_test)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _test(self):
        token = self._token_input.text().strip()
        chat_raw = self._chat_input.text().strip()
        chat_ids = [c.strip() for c in chat_raw.split(",") if c.strip()]
        if not token or not chat_ids:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng nhập Bot Token và Chat ID!")
            return

        self.notifier.bot_token = token
        self.notifier.telegram_chat_ids = chat_ids
        ok = self.notifier.send_message("✨ <b>TCD REUP TOOL:</b> Kết nối Telegram Bot thành công!")
        if ok:
            QMessageBox.information(self, "Thành Công", "Đã gửi tin nhắn test thành công tới Telegram!")
        else:
            QMessageBox.critical(self, "Thất Bại", "Gửi tin nhắn thất bại. Vui lòng kiểm tra lại Token & Chat ID.")

    def _save(self):
        token = self._token_input.text().strip()
        chat_raw = self._chat_input.text().strip()
        self.notifier.bot_token = token
        self.notifier.telegram_chat_ids = [c.strip() for c in chat_raw.split(",") if c.strip()]
        self.notifier.save_telegram_map(self.config_path)
        self.accept()


class LicenseDialog(QDialog):
    """Terms and License information dialog."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Điều Khoản & Bản Quyền TCD REUP TOOL")
        self.setFixedSize(500, 360)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QLabel("<b style='font-size:16px; color:#FBBF24;'>🔐 THÔNG TIN BẢN QUYỀN VIP PRO</b>")
        layout.addWidget(header)

        info_box = QFrame()
        info_box.setStyleSheet("background-color: #111823; border: 1px solid #2A3B52; border-radius: 8px; padding: 12px;")
        ib_layout = QVBoxLayout(info_box)
        ib_layout.setSpacing(8)

        ib_layout.addWidget(QLabel("• <b>Trạng Thái:</b> <span style='color:#10B981;'>VIP PRO ĐÃ KÍCH HOẠT VĨNH VIỄN</span>"))
        ib_layout.addWidget(QLabel("• <b>Thời Hạn Sử Dụng:</b> Vĩnh viễn"))
        ib_layout.addWidget(QLabel("• <b>Ngày Hết Hạn:</b> Không hạn"))
        ib_layout.addWidget(QLabel("• <b>Mã Phần Cứng (HWID):</b> <code style='color:#38BDF8;'>7F9353327262</code>"))
        ib_layout.addWidget(QLabel("• <b>Mã Ổ Cứng (Drive ID):</b> <code style='color:#38BDF8;'>1902-0818</code>"))
        layout.addWidget(info_box)

        support_card = QLabel(
            "📞 <b>Nhà Phát Triển & Hỗ Trợ Kỹ Thuật:</b><br>"
            "• Tác giả: <b>Thanh Code Dao</b> (Hotline / Zalo: <b style='color:#38BDF8;'>@thanhcodedao</b>)<br>"
            "• Phiên bản Engine: <b>v1.0</b>"
        )
        support_card.setStyleSheet("color:#CBD5E1; font-size:12px;")
        layout.addWidget(support_card)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("Xác Nhận")
        btn_ok.setObjectName("btn_primary")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)


class MainWindow(QMainWindow):
    """
    Main Window reproducing the authentic TCD REUP TOOL interface.
    """
    def __init__(self, base_path: str = "", license_info: dict = None, parent=None):
        super().__init__(parent)
        self.base_path = base_path or os.path.dirname(os.path.abspath(__file__))
        self.license_info = license_info or {}
        
        # Exact window title as captured in the authentic system screenshot
        self.setWindowTitle("Thanh Code Dao @thanhcodedao | License - Vĩnh viễn | TCD REUP TOOL")
        self.setMinimumSize(1120, 780)
        self.setStyleSheet(TCD_NAVY_QSS)

        # Managers & state
        self.config_dir = os.path.join(self.base_path, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.project_manager = ProjectManager(self.base_path)

        self.telegram_config_path = os.path.join(self.config_dir, "telegram_config.json")
        if not os.path.exists(self.telegram_config_path) and os.path.exists(os.path.join(self.base_path, "telegram_config.json")):
            self.telegram_config_path = os.path.join(self.base_path, "telegram_config.json")
        self.telegram_notifier = TelegramNotifier()
        self.telegram_notifier.load_telegram_map(self.telegram_config_path)

        self.api_keys_path = os.path.join(self.config_dir, "api_keys.json")
        if not os.path.exists(self.api_keys_path) and os.path.exists(os.path.join(self.base_path, "api_keys.json")):
            self.api_keys_path = os.path.join(self.base_path, "api_keys.json")
        self.api_key_manager = APIKeyManager(config_path=self.api_keys_path)

        self.gpm_port = "9222"
        self._worker: Optional[AutomationWorker] = None

        self._init_ui()
        self._load_active_project()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 10, 14, 12)
        main_layout.setSpacing(10)

        # 0. TOP VIP STATUS HEADER
        top_banner = QFrame()
        top_banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #162235, stop:0.5 #131B2A, stop:1 #162235);
                border: 1px solid #233752;
                border-radius: 8px;
                padding: 4px 10px;
            }
        """)
        tb_layout = QHBoxLayout(top_banner)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(10)

        tb_left = QLabel("<b style='color:#FBBF24; font-size:13px;'>⚡ TCD REUP TOOL v2.5</b> <span style='color:#64748B;'>|</span> <span style='color:#94A3B8; font-size:11px;'>Tác giả: <b>Thanh Code Dao</b> (Zalo/Hotline: <b style='color:#38BDF8;'>@thanhcodedao</b>)</span>")
        tb_layout.addWidget(tb_left)
        tb_layout.addStretch()

        tb_right = QLabel("<span style='background-color:#064E3B; border:1px solid #10B981; color:#34D399; font-weight:bold; font-size:11px; padding:3px 10px; border-radius:10px;'>● VIP PRO VĨNH VIỄN</span>")
        tb_layout.addWidget(tb_right)
        main_layout.addWidget(top_banner)

        # 1. TOP BAR: Dự án & Cài đặt mạng
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Project Box (Left)
        proj_group = QGroupBox("Dự án")
        proj_layout = QHBoxLayout(proj_group)
        proj_layout.setContentsMargins(10, 10, 10, 10)
        proj_layout.setSpacing(8)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(140)
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        proj_layout.addWidget(self._project_combo)

        btn_create_proj = QPushButton("➕ Tạo dự án")
        btn_create_proj.clicked.connect(self._open_create_project_dialog)
        proj_layout.addWidget(btn_create_proj)

        btn_manage_proj = QPushButton("📁 Quản lý dự án")
        btn_manage_proj.clicked.connect(self._open_manage_projects_dialog)
        proj_layout.addWidget(btn_manage_proj)

        top_row.addWidget(proj_group, 3)

        # Network Settings (Right)
        net_group = QGroupBox("Cài đặt mạng")
        net_layout = QHBoxLayout(net_group)
        net_layout.setContentsMargins(10, 10, 10, 10)
        net_layout.setSpacing(12)

        self._proxy_radio = QRadioButton("🔘 Dùng Proxy")
        self._proxy_radio.setChecked(False)
        self._proxy_radio.toggled.connect(self._on_proxy_toggled)
        net_layout.addWidget(self._proxy_radio)

        net_layout.addWidget(QLabel("Vùng:"))
        self._region_combo = QComboBox()
        self._region_combo.addItems([
            "IP - Nhật Bản",
            "IP - Hoa Kỳ",
            "IP - Việt Nam",
            "IP - Hàn Quốc",
            "IP - Singapore",
            "IP - Đức"
        ])
        net_layout.addWidget(self._region_combo)
        net_layout.addStretch()

        top_row.addWidget(net_group, 2)
        main_layout.addLayout(top_row)

        # 2. KÊNH THEO DÕI SECTION
        channels_group = QGroupBox("Kênh theo dõi")
        ch_layout = QVBoxLayout(channels_group)
        ch_layout.setContentsMargins(10, 12, 10, 10)
        ch_layout.setSpacing(8)

        self._channel_table = QTableWidget(0, 4)
        self._channel_table.setHorizontalHeaderLabels(["#", "📺 Link Kênh YouTube", "⚡ Trạng Thái", "🕒 Lần Quét Cuối"])
        self._channel_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._channel_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._channel_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._channel_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._channel_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._channel_table.setAlternatingRowColors(True)
        self._channel_table.setShowGrid(False)
        self._channel_table.verticalHeader().setDefaultSectionSize(30)
        self._channel_table.setFixedHeight(135)
        ch_layout.addWidget(self._channel_table)

        # Input & Controls Row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._channel_input = QLineEdit()
        self._channel_input.setPlaceholderText("Nhập link kênh YouTube (VD: https://youtube.com/@channel)...")
        self._channel_input.returnPressed.connect(self._add_channel)
        input_row.addWidget(self._channel_input, 4)

        btn_add_ch = QPushButton("➕ Thêm kênh")
        btn_add_ch.clicked.connect(self._add_channel)
        input_row.addWidget(btn_add_ch)

        btn_del_ch = QPushButton("🗑 Xóa kênh")
        btn_del_ch.clicked.connect(self._delete_channel)
        input_row.addWidget(btn_del_ch)

        self._btn_start = QPushButton("▶ Bắt đầu")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.clicked.connect(self._start_automation)
        input_row.addWidget(self._btn_start)

        self._btn_stop = QPushButton("⏹ Dừng")
        self._btn_stop.setObjectName("btn_stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_automation)
        input_row.addWidget(self._btn_stop)

        input_row.addWidget(QLabel("Luồng:"))
        self._threads_spin = QSpinBox()
        self._threads_spin.setRange(1, 2000)
        self._threads_spin.setValue(500)
        self._threads_spin.setFixedWidth(70)
        input_row.addWidget(self._threads_spin)

        btn_help = QPushButton("?")
        btn_help.setFixedSize(26, 26)
        btn_help.setToolTip("Số luồng worker đồng thời (Mặc định: 500)")
        btn_help.clicked.connect(lambda: QMessageBox.information(self, "Thông Tin Luồng", "Cấu hình số luồng chạy song song để tối ưu tốc độ quét kênh và render video."))
        input_row.addWidget(btn_help)

        ch_layout.addLayout(input_row)
        main_layout.addWidget(channels_group)

        # 3. MIDDLE SPLIT: Logs (Left) & YouTube API Quota (Right)
        mid_row = QHBoxLayout()
        mid_row.setSpacing(10)

        # Left: Logs & Stylized Brand
        log_frame = QFrame()
        log_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141E2F, stop:1 #101826);
                border: 1px solid #1F2F47;
                border-radius: 9px;
            }
        """)
        lf_layout = QVBoxLayout(log_frame)
        lf_layout.setContentsMargins(10, 8, 10, 8)
        lf_layout.setSpacing(6)

        lf_header = QHBoxLayout()
        lf_header.addWidget(QLabel("<b style='color:#38BDF8; font-size:12px;'>● CONSOLE LOGS & TIẾN TRÌNH THỰC THI</b>"))
        lf_header.addStretch()

        btn_clear_log = QPushButton("🧹 Xóa log")
        btn_clear_log.setFixedHeight(22)
        btn_clear_log.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        btn_clear_log.clicked.connect(lambda: self._log_view.clear())
        lf_header.addWidget(btn_clear_log)
        lf_layout.addLayout(lf_header)

        # Watermark Banner above Console
        brand_bar = QLabel(
            "<div style='text-align:center; padding:3px 6px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0F172A,stop:0.5 #1E3A8A,stop:1 #0F172A); border:1px solid #2563EB; border-radius:5px;'>"
            "<b style='color:#FBBF24; font-size:12px;'>[ ▶ TCD REUP TOOL ]</b> "
            "<span style='color:#93C5FD; font-size:11px;'>YouTube to TikTok Automation Engine • GPMLogin CDP v1.0</span>"
            "</div>"
        )
        lf_layout.addWidget(brand_bar)

        self._log_view = QTextEdit()
        self._log_view.setObjectName("console_log")
        self._log_view.setReadOnly(True)
        self._log_view.setFixedHeight(120)
        lf_layout.addWidget(self._log_view)

        mid_row.addWidget(log_frame, 3)

        # Right: API Key Quota & Controls
        api_frame = QFrame()
        api_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141E2F, stop:1 #101826);
                border: 1px solid #1F2F47;
                border-radius: 9px;
            }
        """)
        af_layout = QVBoxLayout(api_frame)
        af_layout.setContentsMargins(12, 10, 12, 10)
        af_layout.setSpacing(8)

        af_title = QLabel("<b>⚡ YouTube Data API v3</b>")
        af_title.setStyleSheet("color: #38BDF8; font-size: 13px;")
        af_layout.addWidget(af_title)

        self._rate_limit_lbl = QLabel("⚡ Key rate limit (0)")
        self._rate_limit_lbl.setStyleSheet("color: #FBBF24; font-weight: bold; font-size: 12px;")
        af_layout.addWidget(self._rate_limit_lbl)

        self._api_info_lbl = QLabel("Hạn mức: 10,000 units/key/ngày")
        self._api_info_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        af_layout.addWidget(self._api_info_lbl)

        btn_manage_api = QPushButton("🔑 Quản Lý API Keys")
        btn_manage_api.clicked.connect(self._open_api_manager_dialog)
        af_layout.addWidget(btn_manage_api)
        af_layout.addStretch()

        mid_row.addWidget(api_frame, 2)
        main_layout.addLayout(mid_row)

        # 4. HÀNG CHỜ TẢI SECTION
        queue_group = QGroupBox("Hàng chờ tải")
        q_layout = QVBoxLayout(queue_group)
        q_layout.setContentsMargins(10, 12, 10, 10)
        q_layout.setSpacing(6)

        self._queue_table = QTableWidget(0, 4)
        self._queue_table.setHorizontalHeaderLabels(["ID Video", "🎬 Tiêu Đề Video", "📊 Tiến Độ", "✨ Trạng Thái"])
        self._queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._queue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._queue_table.setAlternatingRowColors(True)
        self._queue_table.setShowGrid(False)
        self._queue_table.verticalHeader().setDefaultSectionSize(30)
        self._queue_table.setFixedHeight(120)
        q_layout.addWidget(self._queue_table)

        main_layout.addWidget(queue_group)

        # 5. BOTTOM BAR / FOOTER: TikTok | Expiration Info | Telegram
        footer_row = QHBoxLayout()
        footer_row.setSpacing(12)

        # TikTok Box (Left)
        tiktok_group = QGroupBox("TikTok")
        tt_layout = QHBoxLayout(tiktok_group)
        tt_layout.setContentsMargins(10, 10, 10, 10)
        tt_layout.setSpacing(10)

        self._tiktok_auto_cb = QCheckBox("✔ Tự động đăng")
        self._tiktok_auto_cb.setChecked(True)
        tt_layout.addWidget(self._tiktok_auto_cb)

        self._tiktok_short_cb = QCheckBox("✔ Chỉ Short")
        self._tiktok_short_cb.setChecked(True)
        tt_layout.addWidget(self._tiktok_short_cb)

        btn_cfg_tiktok = QPushButton("⚙️ Cấu hình TikTok")
        btn_cfg_tiktok.clicked.connect(self._open_tiktok_config)
        tt_layout.addWidget(btn_cfg_tiktok)

        btn_license = QPushButton("💳 Điều khoản _ Bản quyền")
        btn_license.setObjectName("btn_license")
        btn_license.clicked.connect(self._open_license_dialog)
        tt_layout.addWidget(btn_license)

        footer_row.addWidget(tiktok_group, 4)

        # License Expiry Center Indicator (Glowing Cyber Green)
        exp_frame = QFrame()
        exp_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #064E3B, stop:1 #022C22);
                border: 1px solid #10B981;
                border-radius: 9px;
            }
        """)
        ef_layout = QVBoxLayout(exp_frame)
        ef_layout.setContentsMargins(14, 8, 14, 8)
        ef_layout.setSpacing(2)

        lbl_days = QLabel("<b style='color:#34D399; font-size:16px;'>Vĩnh viễn</b>")
        lbl_days.setAlignment(Qt.AlignCenter)
        ef_layout.addWidget(lbl_days)

        lbl_exp_date = QLabel("<span style='color:#A7F3D0; font-size:11px;'>● Hết hạn: Không hạn</span>")
        lbl_exp_date.setAlignment(Qt.AlignCenter)
        ef_layout.addWidget(lbl_exp_date)

        footer_row.addWidget(exp_frame, 2)

        # Telegram Box (Right)
        tele_group = QGroupBox("Telegram")
        tl_layout = QHBoxLayout(tele_group)
        tl_layout.setContentsMargins(10, 10, 10, 10)
        tl_layout.setSpacing(8)

        self._tele_cb = QCheckBox("✔ Gửi thông báo")
        self._tele_cb.setChecked(self.telegram_notifier.enabled)
        self._tele_cb.toggled.connect(self._on_tele_toggled)
        tl_layout.addWidget(self._tele_cb)

        btn_link_tele = QPushButton("🔗 Liên kết")
        btn_link_tele.clicked.connect(self._open_telegram_config)
        tl_layout.addWidget(btn_link_tele)

        btn_unlink_tele = QPushButton("🔌 Ngắt kết nối")
        btn_unlink_tele.clicked.connect(self._unlink_telegram)
        tl_layout.addWidget(btn_unlink_tele)

        btn_test_tele = QPushButton("✈ Test Tele")
        btn_test_tele.clicked.connect(self._test_telegram_fast)
        tl_layout.addWidget(btn_test_tele)

        footer_row.addWidget(tele_group, 4)
        main_layout.addLayout(footer_row)

        # Initial logs matching screenshot
        self.append_log("🎵 TikTok Upload: BẬT")
        self.append_log("📢 Đã bật thông báo Telegram")
        self.append_log("📁 Đã nạp lịch tự động từ database/cache")
        self._update_api_status()

        self._tele_cb = QCheckBox("✔ Gửi thông báo")
        self._tele_cb.setChecked(self.telegram_notifier.enabled)
        self._tele_cb.toggled.connect(self._on_tele_toggled)
        tl_layout.addWidget(self._tele_cb)

        btn_link_tele = QPushButton("Liên kết")
        btn_link_tele.clicked.connect(self._open_telegram_config)
        tl_layout.addWidget(btn_link_tele)

        btn_unlink_tele = QPushButton("Ngắt kết nối")
        btn_unlink_tele.clicked.connect(self._unlink_telegram)
        tl_layout.addWidget(btn_unlink_tele)

        btn_test_tele = QPushButton("Test Tele")
        btn_test_tele.clicked.connect(self._test_telegram_fast)
        tl_layout.addWidget(btn_test_tele)

        footer_row.addWidget(tele_group, 4)
        main_layout.addLayout(footer_row)

        # Initial logs matching screenshot
        self.append_log("🎵 TikTok Upload: BẬT")
        self.append_log("📢 Đã bật thông báo Telegram")
        self.append_log("📁 Đã nạp lịch tự động từ database/cache")
        self._update_api_status()

    # --- Project Management Slots ---

    def _refresh_projects_combo(self):
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        projects = self.project_manager.list_projects()
        self._project_combo.addItems(projects)
        idx = self._project_combo.findText(self.project_manager.active_project)
        if idx >= 0:
            self._project_combo.setCurrentIndex(idx)
        self._project_combo.blockSignals(False)

    def _load_active_project(self):
        self._refresh_projects_combo()
        pdata = self.project_manager.load_project()
        
        # Load channels
        self._channel_table.setRowCount(0)
        channels = pdata.get("channels", [])
        for ch in channels:
            self._insert_channel_row(ch)

        # Load settings
        self._threads_spin.setValue(pdata.get("threads", 500))
        self._proxy_radio.setChecked(pdata.get("use_proxy", False))
        region = pdata.get("proxy_region", "IP - Nhật Bản")
        r_idx = self._region_combo.findText(region)
        if r_idx >= 0:
            self._region_combo.setCurrentIndex(r_idx)

        self._tiktok_auto_cb.setChecked(pdata.get("auto_upload_tiktok", True))
        self._tiktok_short_cb.setChecked(pdata.get("only_shorts", True))
        self._tele_cb.setChecked(pdata.get("telegram_enabled", True))

        self.append_log(f"📁 Đang làm việc trên dự án: <b>{self.project_manager.active_project}</b> ({len(channels)} kênh)")

    def _save_active_project_state(self):
        channels = []
        for r in range(self._channel_table.rowCount()):
            item = self._channel_table.item(r, 1)
            if item:
                channels.append(item.text().strip())

        pdata = {
            "name": self.project_manager.active_project,
            "channels": channels,
            "threads": self._threads_spin.value(),
            "use_proxy": self._proxy_radio.isChecked(),
            "proxy_region": self._region_combo.currentText(),
            "auto_upload_tiktok": self._tiktok_auto_cb.isChecked(),
            "only_shorts": self._tiktok_short_cb.isChecked(),
            "telegram_enabled": self._tele_cb.isChecked(),
            "queue": []
        }
        self.project_manager.save_project(data=pdata)

    def _on_project_changed(self):
        new_proj = self._project_combo.currentText()
        if new_proj and new_proj != self.project_manager.active_project:
            self._save_active_project_state()
            self.project_manager.switch_project(new_proj)
            self._load_active_project()

    def _open_create_project_dialog(self):
        dlg = CreateProjectDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.project_name:
            if self.project_manager.create_project(dlg.project_name):
                self._load_active_project()
                self.append_log(f"✨ Đã tạo và chuyển sang dự án mới: <b>{dlg.project_name}</b>")
                QMessageBox.information(self, "Thành Công", f"Dự án '{dlg.project_name}' đã được tạo thành công!")
            else:
                QMessageBox.warning(self, "Đã Tồn Tại", f"Dự án '{dlg.project_name}' đã tồn tại từ trước!")

    def _open_manage_projects_dialog(self):
        curr_key = self.api_key_manager.get_current_key() or ""
        dlg = ManageProjectsDialog(self.project_manager, api_key=curr_key, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._load_active_project()

    # --- Channels Table Operations ---

    def _insert_channel_row(self, url: str):
        row = self._channel_table.rowCount()
        self._channel_table.insertRow(row)
        
        stt_item = QTableWidgetItem(f"{row + 1:02d}")
        stt_item.setTextAlignment(Qt.AlignCenter)
        stt_item.setForeground(QColor("#94A3B8"))
        self._channel_table.setItem(row, 0, stt_item)

        url_item = QTableWidgetItem(url)
        url_item.setForeground(QColor("#F8FAFC"))
        self._channel_table.setItem(row, 1, url_item)

        status_item = QTableWidgetItem("● Sẵn sàng")
        status_item.setForeground(QColor("#34D399"))
        status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        status_item.setTextAlignment(Qt.AlignCenter)
        self._channel_table.setItem(row, 2, status_item)

        now_str = datetime.now().strftime("%H:%M:%S")
        time_item = QTableWidgetItem(now_str)
        time_item.setForeground(QColor("#64748B"))
        time_item.setTextAlignment(Qt.AlignCenter)
        self._channel_table.setItem(row, 3, time_item)

    def _add_channel(self):
        url = self._channel_input.text().strip()
        if not url:
            return
        self._insert_channel_row(url)
        self._channel_input.clear()
        self._save_active_project_state()
        self.append_log(f"📺 Đã thêm kênh mới: {url}")

    def _delete_channel(self):
        row = self._channel_table.currentRow()
        if row >= 0:
            url_item = self._channel_table.item(row, 1)
            url_text = url_item.text() if url_item else ""
            self._channel_table.removeRow(row)
            # Re-index STT
            for r in range(self._channel_table.rowCount()):
                self._channel_table.item(r, 0).setText(str(r + 1))
            self._save_active_project_state()
            self.append_log(f"🗑 Đã xóa kênh: {url_text}")

    # --- Logging & Status Helpers ---

    def append_log(self, text: str):
        now = datetime.now().strftime("%H:%M:%S")
        if "Lỗi" in text or "Error" in text or "Failed" in text or "❌" in text:
            color = "#FB7185"
            badge = "<span style='background-color:#4C0519; color:#FB7185; padding:1px 5px; border-radius:3px; font-weight:bold; font-size:10px;'>ERR</span>"
        elif "thành công" in text or "Success" in text or "✨" in text or "✅" in text:
            color = "#34D399"
            badge = "<span style='background-color:#064E3B; color:#34D399; padding:1px 5px; border-radius:3px; font-weight:bold; font-size:10px;'>SUCCESS</span>"
        elif "Cảnh báo" in text or "Warning" in text or "⚠️" in text:
            color = "#FBBF24"
            badge = "<span style='background-color:#451A03; color:#FBBF24; padding:1px 5px; border-radius:3px; font-weight:bold; font-size:10px;'>WARN</span>"
        elif "🎵" in text or "TikTok" in text:
            color = "#C084FC"
            badge = "<span style='background-color:#2E1065; color:#C084FC; padding:1px 5px; border-radius:3px; font-weight:bold; font-size:10px;'>TIKTOK</span>"
        elif "📢" in text or "Telegram" in text:
            color = "#38BDF8"
            badge = "<span style='background-color:#0C4A6E; color:#38BDF8; padding:1px 5px; border-radius:3px; font-weight:bold; font-size:10px;'>TELE</span>"
        else:
            color = "#E2E8F0"
            badge = "<span style='background-color:#1E293B; color:#94A3B8; padding:1px 5px; border-radius:3px; font-weight:bold; font-size:10px;'>INFO</span>"

        html = f"<span style='color:#64748B;'>[{now}]</span> {badge} <span style='color:{color}; font-size:12px;'>{text}</span>"
        self._log_view.append(html)
        self._log_view.ensureCursorVisible()

    def append_status_text(self, text: str):
        """Backward compatibility alias for append_log."""
        self.append_log(text)

    def _update_api_status(self):
        from src.services.api_pool_manager import APIPoolManager
        pm = APIPoolManager(self.base_path)
        total = pm.get_total_count()
        remaining = pm.get_remaining_count()
        dead = len(pm.dead_keys)
        self._rate_limit_lbl.setText(f"⚡ Key rate limit / chết ({dead})")
        if total > 0:
            self._api_info_lbl.setText(f"Kho: {total} keys | Còn lại: {remaining}")
        else:
            self._api_info_lbl.setText("Chưa nạp kho API (Bấm để mở Quản lý API)")

    def _open_api_manager_dialog(self):
        from src.ui.api_distributor_dialog import APIDistributorDialog
        dlg = APIDistributorDialog(self.base_path, self)
        dlg.exec_()
        self._update_api_status()
        self.append_log("🔄 Đã đồng bộ cấu hình kho API YouTube v3.")

    def _open_tiktok_config(self):
        from src.ui.tiktok_config_dialog import TikTokProjectConfigDialog
        dlg = TikTokProjectConfigDialog(self.project_manager, self)
        if dlg.exec_() == QDialog.Accepted:
            self.append_log(f"🚀 Đã cập nhật cấu hình TikTok Upload cho dự án '{self.project_manager.active_project}'.")

    def _open_license_dialog(self):
        dlg = LicenseDialog(self)
        dlg.exec_()

    def _open_telegram_config(self):
        dlg = TelegramConfigDialog(self.telegram_notifier, self.telegram_config_path, self)
        if dlg.exec_() == QDialog.Accepted:
            self.append_log("📢 Đã lưu cấu hình kết nối Telegram.")

    def _unlink_telegram(self):
        self.telegram_notifier.enabled = False
        self._tele_cb.setChecked(False)
        self.append_log("🔕 Đã ngắt kết nối thông báo Telegram.")
        QMessageBox.information(self, "Telegram", "Đã ngắt kết nối thông báo Telegram.")

    def _test_telegram_fast(self):
        if not self.telegram_notifier.bot_token or not self.telegram_notifier.telegram_chat_ids:
            self._open_telegram_config()
            return
        ok = self.telegram_notifier.send_message("✨ <b>TCD REUP TOOL:</b> Tin nhắn kiểm tra kết nối nhanh thành công!")
        if ok:
            self.append_log("✈ Gửi tin nhắn test Telegram thành công.")
            QMessageBox.information(self, "Thành Công", "Gửi tin nhắn test Telegram thành công!")
        else:
            self.append_log("❌ Lỗi gửi tin nhắn Telegram.")
            QMessageBox.critical(self, "Thất Bại", "Gửi tin nhắn test Telegram thất bại. Kiểm tra lại cấu hình!")

    def _on_proxy_toggled(self, checked: bool):
        self._save_active_project_state()
        status = "BẬT" if checked else "TẮT"
        self.append_log(f"🌐 Chế độ Proxy: {status} ({self._region_combo.currentText()})")

    def _on_tele_toggled(self, checked: bool):
        self.telegram_notifier.enabled = checked
        self._save_active_project_state()
        status = "BẬT" if checked else "TẮT"
        self.append_log(f"📢 Thông báo Telegram: {status}")

    # --- Automation Worker Execution ---

    def _start_automation(self):
        if self._channel_table.rowCount() == 0:
            QMessageBox.warning(self, "Chưa Có Kênh", "Vui lòng nhập ít nhất 1 URL kênh YouTube trước khi chạy!")
            return

        channels = []
        for r in range(self._channel_table.rowCount()):
            item = self._channel_table.item(r, 1)
            if item:
                channels.append(item.text().strip())

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self.append_log("▶ Bắt đầu khởi chạy Worker tự động hóa đa kênh...")

        pdata = self.project_manager.load_project()
        proj_schedule = pdata.get("schedule", [])
        tt_config = self.project_manager.get_tiktok_config()

        self._worker = AutomationWorker(
            channels=channels,
            base_path=self.base_path,
            auto_upload_tiktok=self._tiktok_auto_cb.isChecked(),
            gpm_port=self.gpm_port,
            telegram_notifier=self.telegram_notifier if self._tele_cb.isChecked() else None,
            api_key_manager=self.api_key_manager,
            schedule=proj_schedule,
            tiktok_config=tt_config,
            parent=self
        )
        self._worker.log_signal.connect(self.append_log)
        self._worker.queue_add_signal.connect(self._on_queue_item_added)
        self._worker.finished_signal.connect(self._stop_automation)
        self._worker.start()

        if self._tele_cb.isChecked() and self.telegram_notifier.enabled:
            self.telegram_notifier.send_message(f"🚀 <b>TCD REUP TOOL:</b> Dự án <b>{self.project_manager.active_project}</b> bắt đầu quét {len(channels)} kênh.")

    def _stop_automation(self):
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self.append_log("⏹ Đã dừng toàn bộ luồng tự động hóa.")

    def _on_queue_item_added(self, item_text: str):
        row = self._queue_table.rowCount()
        self._queue_table.insertRow(row)
        
        vid_id_match = re.search(r"\(ID:\s*([^\)]+)\)", item_text)
        vid_id = vid_id_match.group(1) if vid_id_match else f"VID_{row+1:02d}"

        id_item = QTableWidgetItem(vid_id)
        id_item.setTextAlignment(Qt.AlignCenter)
        id_item.setForeground(QColor("#38BDF8"))
        id_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._queue_table.setItem(row, 0, id_item)

        title_item = QTableWidgetItem(item_text)
        title_item.setForeground(QColor("#F1F5F9"))
        self._queue_table.setItem(row, 1, title_item)

        prog_item = QTableWidgetItem("100%")
        prog_item.setTextAlignment(Qt.AlignCenter)
        prog_item.setForeground(QColor("#10B981"))
        prog_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._queue_table.setItem(row, 2, prog_item)

        st_item = QTableWidgetItem("● Hoàn tất")
        st_item.setTextAlignment(Qt.AlignCenter)
        st_item.setForeground(QColor("#34D399"))
        st_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._queue_table.setItem(row, 3, st_item)
