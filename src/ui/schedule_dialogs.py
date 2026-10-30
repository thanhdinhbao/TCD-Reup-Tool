"""
Schedule Dialogs for TCD REUP TOOL.
Implements the Schedule Analysis Mode Selection Dialog and Schedule Manager.
Faithfully reproduces the authentic commercial interface.
"""
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QListWidget,
    QTimeEdit, QMessageBox, QFrame, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QTime
from src.ui.theme import TCD_NAVY_QSS


class ScheduleModeDialog(QDialog):
    """
    Modal dialog matching Image 2:
    '📊 Chọn chế độ phân tích'
    Allows choosing between 'TÁCH CỤM', 'Gộp tất cả' and 'Quét tất cả thời gian'.
    """
    def __init__(self, project_name: str, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.selected_mode = "multi"  # 'multi', 'single', or 'all_time'
        self.setWindowTitle("📊 Chọn chế độ phân tích")
        self.setFixedSize(520, 480)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header with Project Name
        title_lbl = QLabel(f"<b style='font-size:16px; color:#FBBF24;'>⭐ Dự án: {self.project_name}</b>")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("Chọn cách gộp khung giờ phân tích lịch đăng video:")
        sub_lbl.setStyleSheet("color:#CBD5E1; font-size:13px; font-weight:600;")
        layout.addWidget(sub_lbl)

        # Group Cards
        self._card1 = QFrame()
        self._card1.setCursor(Qt.PointingHandCursor)
        self._card1.mousePressEvent = lambda e: self._select_mode("multi")
        c1_layout = QVBoxLayout(self._card1)
        c1_layout.setContentsMargins(14, 12, 14, 12)
        c1_layout.setSpacing(6)

        c1_header = QHBoxLayout()
        c1_title = QLabel("<b style='font-size:14px; color:#38BDF8;'>📊 TÁCH CỤM</b>")
        c1_badge = QLabel("<b style='background-color:#065F46; color:#34D399; padding:2px 6px; border-radius:4px; font-size:10px;'>KHUYÊN DÙNG</b>")
        c1_header.addWidget(c1_title)
        c1_header.addWidget(c1_badge)
        c1_header.addStretch()
        c1_layout.addLayout(c1_header)

        c1_desc = QLabel(
            "Gộp các video cách nhau <b>&lt; 60 phút</b> thành 1 cụm. Tạo nhiều khung giờ riêng biệt, "
            "tiết kiệm thời gian chạy & giảm tải RAM khi mở GPM.<br>"
            "<span style='color:#94A3B8;'>VD: 2 khung 09:00-10:00 và 19:00-20:00</span>"
        )
        c1_desc.setWordWrap(True)
        c1_desc.setStyleSheet("color:#CBD5E1; font-size:11px; line-height:1.4;")
        c1_layout.addWidget(c1_desc)
        layout.addWidget(self._card1)

        self._card2 = QFrame()
        self._card2.setCursor(Qt.PointingHandCursor)
        self._card2.mousePressEvent = lambda e: self._select_mode("single")
        c2_layout = QVBoxLayout(self._card2)
        c2_layout.setContentsMargins(14, 12, 14, 12)
        c2_layout.setSpacing(6)

        c2_title = QLabel("<b style='font-size:14px; color:#E2E8F0;'>🔗 Gộp tất cả</b>")
        c2_layout.addWidget(c2_title)

        c2_desc = QLabel(
            "Gộp <b>TẤT CẢ</b> video thành 1 khung giờ duy nhất. Chạy liên tục từ video sớm nhất đến muộn nhất.<br>"
            "<span style='color:#94A3B8;'>VD: 1 khung 09:00-22:00 (chạy cả ngày)</span>"
        )
        c2_desc.setWordWrap(True)
        c2_desc.setStyleSheet("color:#CBD5E1; font-size:11px; line-height:1.4;")
        c2_layout.addWidget(c2_desc)
        layout.addWidget(self._card2)

        self._card3 = QFrame()
        self._card3.setCursor(Qt.PointingHandCursor)
        self._card3.mousePressEvent = lambda e: self._select_mode("all_time")
        c3_layout = QVBoxLayout(self._card3)
        c3_layout.setContentsMargins(14, 12, 14, 12)
        c3_layout.setSpacing(6)

        c3_title = QLabel("<b style='font-size:14px; color:#34D399;'>⏰ Quét tất cả thời gian (24/7)</b>")
        c3_layout.addWidget(c3_title)

        c3_desc = QLabel(
            "Chạy liên tục <b>toàn bộ thời gian (00:00 - 23:59)</b>, không giới hạn khung giờ. "
            "Tự động quét và đăng ngay lập tức bất cứ lúc nào kênh có video mới.<br>"
            "<span style='color:#94A3B8;'>VD: 1 khung 00:00-23:59 (chạy 24/24 cả ngày)</span>"
        )
        c3_desc.setWordWrap(True)
        c3_desc.setStyleSheet("color:#CBD5E1; font-size:11px; line-height:1.4;")
        c3_layout.addWidget(c3_desc)
        layout.addWidget(self._card3)

        # Style Cards initially
        self._update_cards_style()

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedWidth(85)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("OK")
        btn_ok.setFixedWidth(85)
        btn_ok.setObjectName("btn_primary")
        btn_ok.clicked.connect(self.accept)

        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _select_mode(self, mode: str):
        self.selected_mode = mode
        self._update_cards_style()

    def _update_cards_style(self):
        active_style = "background-color: #1E293B; border: 2px solid #38BDF8; border-radius: 8px;"
        idle_style = "background-color: #151D2A; border: 1px solid #28394E; border-radius: 8px;"

        if self.selected_mode == "multi":
            self._card1.setStyleSheet(active_style)
            self._card2.setStyleSheet(idle_style)
            self._card3.setStyleSheet(idle_style)
        elif self.selected_mode == "all_time":
            self._card1.setStyleSheet(idle_style)
            self._card2.setStyleSheet(idle_style)
            self._card3.setStyleSheet(active_style)
        else:
            self._card1.setStyleSheet(idle_style)
            self._card2.setStyleSheet(active_style)
            self._card3.setStyleSheet(idle_style)


class ScheduleManagerDialog(QDialog):
    """Dialog to view, add, delete, or clear custom schedule windows."""
    def __init__(self, project_name: str, current_schedules: List[Dict[str, str]], parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.schedules = list(current_schedules)
        self.setWindowTitle(f"Quản Lý Lịch Tự Động — Dự án {self.project_name}")
        self.setFixedSize(480, 380)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel(f"<b style='font-size:15px; color:#38BDF8;'>⏰ LỊCH TỰ ĐỘNG CHẠY GPM & TIKTOK</b>")
        layout.addWidget(header)

        sub = QLabel("Hệ thống chỉ khởi động trình duyệt GPM trong các khung giờ dưới đây để tiết kiệm tài nguyên:")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#94A3B8; font-size:11px;")
        layout.addWidget(sub)

        self._list = QListWidget()
        self._list.setStyleSheet("font-size:13px; padding:6px;")
        self._populate_list()
        layout.addWidget(self._list)

        # Add manual slot row
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Từ:"))
        self._t_start = QTimeEdit()
        self._t_start.setTime(QTime(9, 0))
        add_row.addWidget(self._t_start)

        add_row.addWidget(QLabel("Đến:"))
        self._t_end = QTimeEdit()
        self._t_end.setTime(QTime(11, 0))
        add_row.addWidget(self._t_end)

        btn_add = QPushButton("➕ Thêm Khung Giờ")
        btn_add.clicked.connect(self._add_slot)
        add_row.addWidget(btn_add)
        layout.addLayout(add_row)

        btn_row = QHBoxLayout()
        btn_del = QPushButton("🗑 Xóa Khung Chọn")
        btn_del.clicked.connect(self._delete_slot)

        btn_clear = QPushButton("Chạy 24/7 (Xóa lịch)")
        btn_clear.clicked.connect(self._clear_all)

        btn_save = QPushButton("💾 Lưu")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self.accept)

        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _populate_list(self):
        self._list.clear()
        if not self.schedules:
            self._list.addItem("Chưa thiết lập lịch (Đang chạy liên tục 24/7)")
            return

        for idx, s in enumerate(self.schedules):
            self._list.addItem(f"⏰ Khung {idx+1}:  {s['start']} ➔ {s['end']}")

    def _add_slot(self):
        s_str = self._t_start.time().toString("HH:mm")
        e_str = self._t_end.time().toString("HH:mm")
        self.schedules.append({"start": s_str, "end": e_str})
        self._populate_list()

    def _delete_slot(self):
        row = self._list.currentRow()
        if 0 <= row < len(self.schedules):
            self.schedules.pop(row)
            self._populate_list()

    def _clear_all(self):
        self.schedules.clear()
        self._populate_list()
