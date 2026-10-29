"""
Quản Lý API — Chia API YouTube cho tất cả TCD.
High-fidelity implementation of the API Distribution Management Window.
Features live master pool editing, bulk channel scanning, smart quota distribution,
multi-threaded live/dead checking, garbage key recovery, and duplicate inspection.
"""
import os
import sys
import webbrowser
import logging
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QSpinBox, QMessageBox, QFrame,
    QProgressBar, QAbstractItemView, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtGui import QColor, QFont

from src.ui.theme import TCD_NAVY_QSS
from src.core.project_manager import ProjectManager
from src.services.api_pool_manager import APIPoolManager

logger = logging.getLogger(__name__)


class TestAPIWorker(QThread):
    """Background concurrent worker to test YouTube API keys."""
    progress_signal = pyqtSignal(int, int, int, int)  # current, total, alive, dead
    finished_signal = pyqtSignal(list, list)           # alive_keys, dead_keys

    def __init__(self, keys: List[str], max_workers: int = 15, parent=None):
        super().__init__(parent)
        self.keys = keys
        self.max_workers = max_workers
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        total = len(self.keys)
        alive_list = []
        dead_list = []
        tested = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_key = {executor.submit(APIPoolManager.test_single_key, k): k for k in self.keys}
            for future in as_completed(future_to_key):
                if not self._is_running:
                    break
                try:
                    k, is_alive, msg = future.result()
                    tested += 1
                    if is_alive:
                        alive_list.append(k)
                    else:
                        dead_list.append(k)
                    self.progress_signal.emit(tested, total, len(alive_list), len(dead_list))
                except Exception as e:
                    logger.error(f"Error testing key: {e}")
                    tested += 1
                    dead_list.append(future_to_key[future])

        self.finished_signal.emit(alive_list, dead_list)


class EditPoolDialog(QDialog):
    """Dialog to edit/paste the Master API Pool."""
    def __init__(self, pool_manager: APIPoolManager, parent=None):
        super().__init__(parent)
        self.pool_manager = pool_manager
        self.setWindowTitle("Sửa Kho API Tổng")
        self.setMinimumSize(600, 520)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel("<b style='font-size:16px; color:#FBBF24;'>📦 SỬA KHO API YOUTUBE TỔNG</b>")
        layout.addWidget(header)

        desc = QLabel(
            "Dán danh sách các <b>YouTube Data API v3 Key</b> tại đây (mỗi key trên 1 dòng).<br>"
            "Hệ thống sẽ tự động lọc bỏ các key trùng lặp và khoảng trắng thừa."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#94A3B8; font-size:12px;")
        layout.addWidget(desc)

        self._keys_edit = QTextEdit()
        self._keys_edit.setPlaceholderText("Dán các API Key tại đây, mỗi key trên 1 dòng:\nAIzaSy...\nAIzaSy...")
        self._keys_edit.setPlainText("\n".join(self.pool_manager.master_pool))
        self._keys_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._keys_edit)

        self._lbl_count = QLabel(f"Tổng số key hiện tại: <b>{len(self.pool_manager.master_pool)}</b>")
        self._lbl_count.setStyleSheet("color:#38BDF8; font-size:12px;")
        layout.addWidget(self._lbl_count)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton("🧹 Xóa hết")
        btn_clear.clicked.connect(lambda: self._keys_edit.clear())

        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾 Lưu Kho API")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save)

        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _on_text_changed(self):
        raw = self._keys_edit.toPlainText().strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        self._lbl_count.setText(f"Tổng số key đang nhập: <b>{len(lines)}</b>")

    def _save(self):
        raw = self._keys_edit.toPlainText().strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        total, added = self.pool_manager.update_pool_keys(lines)
        QMessageBox.information(self, "Thành Công", f"Đã lưu thành công {total} API Key vào kho tổng!")
        self.accept()


class ViewUnassignedDialog(QDialog):
    """Dialog showing remaining unassigned keys."""
    def __init__(self, unassigned_keys: List[str], parent=None):
        super().__init__(parent)
        self.unassigned = unassigned_keys
        self.setWindowTitle("Danh Sách API Còn Lại (Chưa Gán)")
        self.setMinimumSize(540, 450)
        self.setStyleSheet(TCD_NAVY_QSS)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel(f"<b style='font-size:15px; color:#10B981;'>📄 KHO CÒN LẠI: {len(self.unassigned)} API KEYS</b>")
        layout.addWidget(header)

        self._view = QTextEdit()
        self._view.setReadOnly(True)
        self._view.setPlainText("\n".join(self.unassigned))
        layout.addWidget(self._view)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋 Sao chép toàn bộ")
        btn_copy.clicked.connect(self._copy_all)

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _copy_all(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(self.unassigned))
        QMessageBox.information(self, "Đã Sao Chép", "Đã sao chép danh sách API còn lại vào bộ nhớ đệm (Clipboard)!")


class APIDistributorDialog(QDialog):
    """
    Main Window for 'Quản Lý API — Chia API YouTube cho tất cả TCD'.
    Full pixel-fidelity and rich functional logic.
    """
    def __init__(self, base_path: str, parent=None):
        super().__init__(parent)
        self.base_path = base_path
        self.setWindowTitle("🔍 Quản Lý API — Chia API YouTube cho tất cả TCD")
        self.setMinimumSize(1080, 680)
        self.setStyleSheet(TCD_NAVY_QSS)

        self.pool_manager = APIPoolManager(self.base_path)
        self.project_manager = ProjectManager(self.base_path)
        self._test_worker: Optional[TestAPIWorker] = None

        # Cache of scanned channels: list of (folder_name, channel_url, project_name)
        self._scanned_targets: List[Tuple[str, str, str]] = []

        self._setup_ui()
        self._refresh_stats()
        # Automatically scan projects upon opening
        self._scan_TCD_and_check()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(14)

        # ==========================================
        # LEFT SIDEBAR
        # ==========================================
        left_panel = QFrame()
        left_panel.setFixedWidth(290)
        left_panel.setStyleSheet("background-color: #172232; border: 1px solid #283B52; border-radius: 8px;")
        l_layout = QVBoxLayout(left_panel)
        l_layout.setContentsMargins(12, 12, 12, 12)
        l_layout.setSpacing(12)

        # 1. Kho API Tổng
        lbl_kho = QLabel("<b>📦 Kho API Tổng</b>")
        lbl_kho.setStyleSheet("font-size: 13px; color: #F1F5F9;")
        l_layout.addWidget(lbl_kho)

        self._lbl_pool_stats = QLabel("Tổng: 0 | Còn lại: 0")
        self._lbl_pool_stats.setStyleSheet("color: #94A3B8; font-size: 12px;")
        l_layout.addWidget(self._lbl_pool_stats)

        btn_edit_pool = QPushButton("✏️ Sửa kho API")
        btn_edit_pool.setStyleSheet("""
            background-color: #D97706; border: 1px solid #F59E0B;
            color: #FFFFFF; font-weight: bold; padding: 7px;
        """)
        btn_edit_pool.clicked.connect(self._open_edit_pool)
        l_layout.addWidget(btn_edit_pool)

        btn_view_unassigned = QPushButton("📄 Xem kho còn lại")
        btn_view_unassigned.setStyleSheet("background-color: #1E293B; border: 1px solid #334155; padding: 6px;")
        btn_view_unassigned.clicked.connect(self._open_view_unassigned)
        l_layout.addWidget(btn_view_unassigned)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color: #24354A;")
        l_layout.addWidget(sep1)

        # 2. Số API cho mỗi kênh
        lbl_alloc = QLabel("<b>🔢 Số API cho mỗi kênh:</b>")
        lbl_alloc.setStyleSheet("font-size: 12px; color: #CBD5E1;")
        l_layout.addWidget(lbl_alloc)

        alloc_row = QHBoxLayout()
        self._spin_keys_per_ch = QSpinBox()
        self._spin_keys_per_ch.setRange(1, 1000)
        self._spin_keys_per_ch.setValue(100)
        self._spin_keys_per_ch.setStyleSheet("font-size: 14px; font-weight: bold; color: #38BDF8; padding: 5px;")
        alloc_row.addWidget(self._spin_keys_per_ch)

        lbl_unit = QLabel("API/kênh")
        lbl_unit.setStyleSheet("color: #94A3B8; font-weight: 500;")
        alloc_row.addWidget(lbl_unit)
        l_layout.addLayout(alloc_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #24354A;")
        l_layout.addWidget(sep2)

        # 3. Thao tác Buttons
        lbl_ops = QLabel("<b>🛠 Thao tác</b>")
        lbl_ops.setStyleSheet("font-size: 12px; color: #CBD5E1;")
        l_layout.addWidget(lbl_ops)

        btn_scan = QPushButton("🔍 Quét & Kiểm tra")
        btn_scan.setStyleSheet("""
            background-color: #0F766E; border: 1px solid #14B8A6;
            color: #FFFFFF; font-weight: bold; padding: 7px;
        """)
        btn_scan.clicked.connect(self._scan_TCD_and_check)
        l_layout.addWidget(btn_scan)

        btn_recover = QPushButton("🗑 Thu hồi API rác")
        btn_recover.setStyleSheet("""
            background-color: #BE123C; border: 1px solid #F43F5E;
            color: #FFFFFF; font-weight: bold; padding: 7px;
        """)
        btn_recover.clicked.connect(self._recover_garbage)
        l_layout.addWidget(btn_recover)

        btn_test_live = QPushButton("⚡ Test API sống/chết")
        btn_test_live.setStyleSheet("""
            background-color: #1D4ED8; border: 1px solid #3B82F6;
            color: #FFFFFF; font-weight: bold; padding: 7px;
        """)
        btn_test_live.clicked.connect(self._start_test_api_keys)
        l_layout.addWidget(btn_test_live)

        btn_dist_missing = QPushButton("📥 Chia cho kênh thiếu API")
        btn_dist_missing.setStyleSheet("""
            background-color: #047857; border: 1px solid #10B981;
            color: #FFFFFF; font-weight: bold; padding: 7px;
        """)
        btn_dist_missing.clicked.connect(self._distribute_missing)
        l_layout.addWidget(btn_dist_missing)

        btn_dist_all = QPushButton("🔄 Chia lại TOÀN BỘ")
        btn_dist_all.setStyleSheet("""
            background-color: #059669; border: 1px solid #34D399;
            color: #FFFFFF; font-weight: bold; padding: 7px;
        """)
        btn_dist_all.clicked.connect(self._distribute_all)
        l_layout.addWidget(btn_dist_all)

        btn_dup = QPushButton("⚠️ Chi tiết API trùng")
        btn_dup.setStyleSheet("background-color: #1E293B; border: 1px solid #334155; padding: 6px;")
        btn_dup.clicked.connect(self._check_duplicates)
        l_layout.addWidget(btn_dup)

        btn_clean_bak = QPushButton("🧹 Xóa file backup (.bak)")
        btn_clean_bak.setStyleSheet("background-color: #1E293B; border: 1px solid #334155; padding: 6px;")
        btn_clean_bak.clicked.connect(self._clean_bak)
        l_layout.addWidget(btn_clean_bak)

        # Progress bar for testing
        self._test_progress = QProgressBar()
        self._test_progress.setFixedHeight(12)
        self._test_progress.setTextVisible(False)
        self._test_progress.setStyleSheet("""
            QProgressBar { background-color: #111823; border: 1px solid #233449; border-radius: 4px; }
            QProgressBar::chunk { background-color: #38BDF8; border-radius: 4px; }
        """)
        self._test_progress.setVisible(False)
        l_layout.addWidget(self._test_progress)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet("color: #24354A;")
        l_layout.addWidget(sep3)

        # 4. Thống kê
        lbl_stats_title = QLabel("<b>📊 Thống kê</b>")
        lbl_stats_title.setStyleSheet("font-size: 12px; color: #CBD5E1;")
        l_layout.addWidget(lbl_stats_title)

        self._lbl_summary_stats = QLabel("Chưa quét TCD")
        self._lbl_summary_stats.setWordWrap(True)
        self._lbl_summary_stats.setStyleSheet("color: #94A3B8; font-size: 11px;")
        l_layout.addWidget(self._lbl_summary_stats)

        l_layout.addStretch()

        # 5. Footer Left
        self._lbl_last_time = QLabel("Chia gần nhất: Chưa thực hiện")
        self._lbl_last_time.setStyleSheet("color: #64748B; font-size: 10px;")
        l_layout.addWidget(self._lbl_last_time)

        main_layout.addWidget(left_panel)

        # ==========================================
        # RIGHT MAIN TABLE AREA
        # ==========================================
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #141D2B; border: 1px solid #24354A; border-radius: 8px;")
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(14, 12, 14, 12)
        r_layout.setSpacing(10)

        # Header Right
        r_header = QHBoxLayout()
        r_title = QLabel("<b>📋 Kết quả quét TCD (real-time)</b>")
        r_title.setStyleSheet("font-size: 15px; color: #F1F5F9;")
        r_header.addWidget(r_title)
        r_header.addStretch()
        r_layout.addLayout(r_header)

        r_sub = QLabel("Bấm 'Quét TCD & Kiểm tra' để bắt đầu")
        r_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        r_layout.addWidget(r_sub)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        lbl_filter = QLabel("🔍 Lọc:")
        lbl_filter.setStyleSheet("color: #94A3B8; font-weight: 600;")
        filter_row.addWidget(lbl_filter)

        filter_row.addWidget(QLabel("Dự án:"))
        self._combo_filter_proj = QComboBox()
        self._combo_filter_proj.addItem("── Tất cả ──")
        self._combo_filter_proj.currentIndexChanged.connect(self._apply_table_filters)
        filter_row.addWidget(self._combo_filter_proj)

        filter_row.addWidget(QLabel("Folder:"))
        self._combo_filter_folder = QComboBox()
        self._combo_filter_folder.addItem("── Tất cả ──")
        self._combo_filter_folder.currentIndexChanged.connect(self._apply_table_filters)
        filter_row.addWidget(self._combo_filter_folder)
        filter_row.addStretch()

        r_layout.addLayout(filter_row)

        # Main Table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "#", "Folder TCD", "URL kênh", "Dự án TCD", "API", "Trạng thái"
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(32)
        self._table.doubleClicked.connect(self._on_table_double_clicked)
        r_layout.addWidget(self._table)

        # Footer Hint
        hint_bar = QLabel("💡 <i>Double-click → mở kênh YouTube | Quét TCD ➔ Kiểm tra ➔ Thu hồi rác ➔ Chia API ➔ Xong!</i>")
        hint_bar.setStyleSheet("color: #64748B; font-size: 11px;")
        r_layout.addWidget(hint_bar)

        main_layout.addWidget(right_panel, 1)

    # ==========================================
    # LOGIC IMPLEMENTATION
    # ==========================================

    def _refresh_stats(self):
        """Update numbers on the left sidebar."""
        total = self.pool_manager.get_total_count()
        remaining = self.pool_manager.get_remaining_count()
        self._lbl_pool_stats.setText(f"Tổng: <b>{total}</b> | Còn lại: <b>{remaining}</b>")

        if self.pool_manager.last_distribution_time:
            self._lbl_last_time.setText(f"Chia gần nhất: {self.pool_manager.last_distribution_time}")

    def _open_edit_pool(self):
        dlg = EditPoolDialog(self.pool_manager, self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_stats()
            self._scan_TCD_and_check()

    def _open_view_unassigned(self):
        unassigned = self.pool_manager.get_unassigned_keys()
        dlg = ViewUnassignedDialog(unassigned, self)
        dlg.exec_()

    @pyqtSlot()
    def _scan_TCD_and_check(self):
        """
        Scans all projects created in TCD REUP TOOL, gathers all channel URLs,
        and associates each with its TCD folder and assigned API keys.
        """
        self._scanned_targets.clear()
        projects = self.project_manager.list_projects()

        for proj in projects:
            pdata = self.project_manager.load_project(proj)
            channels = pdata.get("channels", [])
            for idx, ch in enumerate(channels):
                folder_name = f"Folder_{proj}_{idx+1}"
                self._scanned_targets.append((folder_name, ch, proj))

        # Update filter dropdowns
        self._combo_filter_proj.blockSignals(True)
        self._combo_filter_proj.clear()
        self._combo_filter_proj.addItem("── Tất cả ──")
        for p in projects:
            self._combo_filter_proj.addItem(p)
        self._combo_filter_proj.blockSignals(False)

        self._combo_filter_folder.blockSignals(True)
        self._combo_filter_folder.clear()
        self._combo_filter_folder.addItem("── Tất cả ──")
        for f, _, _ in self._scanned_targets:
            self._combo_filter_folder.addItem(f)
        self._combo_filter_folder.blockSignals(False)

        self._populate_table(self._scanned_targets)
        self._refresh_stats()

        # Update summary stats
        total_channels = len(self._scanned_targets)
        assigned_keys = len(self.pool_manager.get_assigned_keys())
        self._lbl_summary_stats.setText(
            f"• Số dự án: <b>{len(projects)}</b><br>"
            f"• Số kênh YouTube: <b>{total_channels}</b><br>"
            f"• Đã gán: <b>{assigned_keys}</b> API keys<br>"
            f"• Key chết: <b>{len(self.pool_manager.dead_keys)}</b>"
        )

    def _populate_table(self, targets: List[Tuple[str, str, str]]):
        """Populate the real-time scan table."""
        self._table.setRowCount(0)
        target_keys_needed = self._spin_keys_per_ch.value()

        for i, (folder, ch_url, proj) in enumerate(targets):
            row = self._table.rowCount()
            self._table.insertRow(row)

            # STT
            stt_item = QTableWidgetItem(str(i + 1))
            stt_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, stt_item)

            # Folder TCD
            f_item = QTableWidgetItem(folder)
            f_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 1, f_item)

            # URL kênh
            url_item = QTableWidgetItem(ch_url)
            self._table.setItem(row, 2, url_item)

            # Dự án TCD
            proj_item = QTableWidgetItem(proj)
            proj_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 3, proj_item)

            # API Keys currently assigned
            assigned_keys = self.pool_manager.channel_map.get(proj, {}).get(ch_url, [])
            count = len(assigned_keys)
            api_item = QTableWidgetItem(f"{count} API")
            api_item.setTextAlignment(Qt.AlignCenter)
            if count >= target_keys_needed:
                api_item.setForeground(QColor("#10B981"))
            elif count > 0:
                api_item.setForeground(QColor("#F59E0B"))
            else:
                api_item.setForeground(QColor("#EF4444"))
            self._table.setItem(row, 4, api_item)

            # Status
            if count >= target_keys_needed:
                st_text = "Đủ API"
                st_color = "#10B981"
            elif count > 0:
                st_text = f"Thiếu ({count}/{target_keys_needed})"
                st_color = "#F59E0B"
            else:
                st_text = "Chưa gán API"
                st_color = "#EF4444"

            st_item = QTableWidgetItem(st_text)
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setForeground(QColor(st_color))
            self._table.setItem(row, 5, st_item)

    def _apply_table_filters(self):
        """Filter rows based on dropdown selections."""
        proj_filter = self._combo_filter_proj.currentText()
        folder_filter = self._combo_filter_folder.currentText()

        filtered = []
        for f, ch, p in self._scanned_targets:
            if proj_filter != "── Tất cả ──" and p != proj_filter:
                continue
            if folder_filter != "── Tất cả ──" and f != folder_filter:
                continue
            filtered.append((f, ch, p))

        self._populate_table(filtered)

    def _on_table_double_clicked(self, index):
        """Double clicking a channel opens its URL in the browser."""
        row = index.row()
        url_item = self._table.item(row, 2)
        if url_item:
            url = url_item.text().strip()
            if url.startswith("http"):
                webbrowser.open(url)
            else:
                QMessageBox.information(self, "Thông Tin Kênh", f"URL kênh: {url}")

    @pyqtSlot()
    def _distribute_all(self):
        """Redistribute entire pool evenly across all channels."""
        if not self._scanned_targets:
            QMessageBox.warning(self, "Chưa Có Kênh", "Không có kênh nào để phân phối API!")
            return

        total_pool = self.pool_manager.get_total_count()
        if total_pool == 0:
            QMessageBox.warning(self, "Kho API Trống", "Kho API tổng đang trống! Vui lòng bấm 'Sửa kho API' để thêm key.")
            return

        keys_per_ch = self._spin_keys_per_ch.value()
        res = self.pool_manager.distribute_all(self._scanned_targets, keys_per_ch)

        self._refresh_stats()
        self._populate_table(self._scanned_targets)

        msg = (
            f"Đã hoàn tất chia lại toàn bộ API:\n"
            f"• Tổng số key đã gán: {res['total_assigned']}\n"
            f"• Kênh nhận đủ {keys_per_ch} key: {res['fully_funded']}\n"
            f"• Kênh nhận một phần: {res['partially_funded']}\n"
            f"• Key còn lại trong kho: {res['remaining_keys']}"
        )
        QMessageBox.information(self, "Phân Phối Thành Công", msg)

    @pyqtSlot()
    def _distribute_missing(self):
        """Distribute remaining keys only to channels that lack sufficient keys."""
        if not self._scanned_targets:
            return

        keys_per_ch = self._spin_keys_per_ch.value()
        res = self.pool_manager.distribute_missing_only(self._scanned_targets, keys_per_ch)

        self._refresh_stats()
        self._populate_table(self._scanned_targets)

        QMessageBox.information(
            self, "Cấp Bổ Sung API",
            f"Đã bổ sung thành công {res['added_keys']} API key vào các kênh còn thiếu!\n"
            f"Còn lại trong kho: {res['remaining_unassigned']} keys."
        )

    @pyqtSlot()
    def _recover_garbage(self):
        """Removes dead/invalid keys from channel mappings and pool."""
        recovered, affected_ch = self.pool_manager.recover_garbage_keys()
        self._refresh_stats()
        self._populate_table(self._scanned_targets)
        QMessageBox.information(
            self, "Thu Hồi API Rác",
            f"Đã thu hồi thành công {recovered} API rác/chết từ {affected_ch} kênh!"
        )

    @pyqtSlot()
    def _check_duplicates(self):
        """Detect and display any keys assigned to multiple channels."""
        duplicates = self.pool_manager.find_duplicate_keys()
        if not duplicates:
            QMessageBox.information(self, "Không Có Key Trùng", "Tuyệt vời! Không có API key nào bị trùng lặp giữa các kênh.")
            return

        details = []
        for k, ch_list in list(duplicates.items())[:10]:
            details.append(f"• Key {k[:14]}... được dùng tại {len(ch_list)} kênh:\n  " + "\n  ".join(ch_list))

        msg = f"Phát hiện {len(duplicates)} API Key bị gán trùng lặp:\n\n" + "\n\n".join(details)
        QMessageBox.warning(self, "Chi Tiết API Trùng Lặp", msg)

    @pyqtSlot()
    def _clean_bak(self):
        """Remove .bak backup files."""
        count = self.pool_manager.clean_backup_files()
        QMessageBox.information(self, "Dọn Dẹp", f"Đã xóa thành công {count} file backup (.bak) tạm thời.")

    @pyqtSlot()
    def _start_test_api_keys(self):
        """Concurrently test API keys against Google YouTube Data API v3 endpoint."""
        keys = self.pool_manager.master_pool
        if not keys:
            QMessageBox.warning(self, "Trống", "Kho API tổng đang trống, không có key để test!")
            return

        self._test_progress.setVisible(True)
        self._test_progress.setMaximum(len(keys))
        self._test_progress.setValue(0)

        self._test_worker = TestAPIWorker(keys, max_workers=15, parent=self)
        self._test_worker.progress_signal.connect(self._on_test_progress)
        self._test_worker.finished_signal.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_progress(self, current: int, total: int, alive: int, dead: int):
        self._test_progress.setValue(current)
        self._lbl_pool_stats.setText(f"Đang test: {current}/{total} | 🟢 Sống: {alive} | 🔴 Chết: {dead}")

    def _on_test_finished(self, alive_keys: list, dead_keys: list):
        self._test_progress.setVisible(False)
        self.pool_manager.alive_keys = set(alive_keys)
        self.pool_manager.dead_keys = set(dead_keys)
        self.pool_manager.save_pool()

        self._refresh_stats()
        QMessageBox.information(
            self, "Kiểm Tra Hoàn Tất",
            f"Kết quả kiểm thử {len(alive_keys) + len(dead_keys)} API keys:\n"
            f"• 🟢 Sống (Hoạt động): {len(alive_keys)}\n"
            f"• 🔴 Chết / Hết Quota: {len(dead_keys)}"
        )
