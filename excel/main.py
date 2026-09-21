import os
import sys
import json
import re
from dataclasses import dataclass
from datetime import datetime
import tempfile
import shutil
from typing import Dict, List, Optional, Tuple, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QSplashScreen,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,

    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from excel_price_tables import (
    TableRegion,
    apply_discount_delta_to_table,
    apply_discount_delta_to_row,
    detect_price_tables,
    parse_discount_ratio,
)
from price_compare import fetch_danawa_lowest_price, write_price_comparison
from erp_client import (
    ERPSession,
    ERPClient,
    InventoryLookupResult,
    format_production_plan_details,
)
from inventory_queue import DEFAULT_INVENTORY_BRIDGE_BASE_URL, InventoryQueueController
from otp_bridge_client import OTPBridgeClient

DEFAULT_OTP_BRIDGE_URL = "http://unione24.co.kr/otp"
APP_STATE_DIRNAME = ".price_table_editor"
SESSION_STATE_FILENAME = "last_session.json"
SESSION_SNAPSHOT_FILENAME = "last_session.xlsx"


class ERPLoginDialog(QDialog):
    def __init__(self, parent: QWidget, session: ERPSession):
        super().__init__(parent)
        self.session = session
        self.otp_poll_start_delay_ms = 7000
        self.otp_poll_start_timer = QTimer(self)
        self.otp_poll_start_timer.setSingleShot(True)
        self.otp_poll_start_timer.timeout.connect(self._start_auto_otp_polling)
        self.otp_poll_start_countdown_timer = QTimer(self)
        self.otp_poll_start_countdown_timer.setInterval(1000)
        self.otp_poll_start_countdown_timer.timeout.connect(self._update_otp_poll_start_countdown)
        self.otp_poll_start_remaining_seconds = 0
        self.otp_poll_timer = QTimer(self)
        self.otp_poll_timer.setInterval(2000)
        self.otp_poll_timer.timeout.connect(self._poll_for_auto_otp)
        self.otp_poll_attempts = 0
        self.otp_poll_limit = 60
        self.otp_auto_verify_in_progress = False
        self.auto_sms_request_attempted = False
        self.setWindowTitle("ERP 로그인")
        self.resize(420, 260)

        self.layout = QVBoxLayout(self)

        self.form = QFormLayout()
        
        saved_id = "E36401"
        saved_pw = "chak4628))"
        try:
            cred_path = _erp_credentials_path()
            if os.path.exists(cred_path):
                with open(cred_path, "r", encoding="utf-8") as f:
                    creds = json.load(f)
                    saved_id = creds.get("id", saved_id)
                    saved_pw = creds.get("pw", saved_pw)
        except Exception:
            pass
            
        self.txt_id = QLineEdit(saved_id)
        self.txt_id.setPlaceholderText("사번 입력 (예: E36401)")
        self.txt_pw = QLineEdit(saved_pw)
        self.txt_pw.setEchoMode(QLineEdit.Password)
        self.txt_pw.setPlaceholderText("비밀번호")

        self.form.addRow("아이디", self.txt_id)
        self.form.addRow("비밀번호", self.txt_pw)

        self.layout.addLayout(self.form)

        self.btn_request_sms = QPushButton("문자 인증번호 받기")
        self.btn_request_sms.clicked.connect(self.on_request_sms)
        self.layout.addWidget(self.btn_request_sms)

        self.auto_otp_group = QGroupBox("자동 OTP 수신")
        auto_form = QFormLayout(self.auto_otp_group)
        self.chk_auto_otp = QCheckBox("자동 OTP 수신 사용")
        default_bridge_url = os.environ.get("OTP_BRIDGE_BASE_URL", "").strip() or DEFAULT_OTP_BRIDGE_URL
        self.chk_auto_otp.setChecked(True)
        self.txt_bridge_url = QLineEdit(default_bridge_url)
        self.txt_bridge_url.setPlaceholderText("예: http://example.com/otp")
        self.lbl_auto_otp_status = QLabel("대기 중")
        self.lbl_auto_otp_status.setWordWrap(True)
        auto_form.addRow(self.chk_auto_otp)
        auto_form.addRow("중계 URL", self.txt_bridge_url)
        auto_form.addRow("상태", self.lbl_auto_otp_status)
        self.layout.addWidget(self.auto_otp_group)

        # OTP Input (Hidden initially)
        self.otp_widget = QWidget()
        self.otp_layout = QHBoxLayout(self.otp_widget)
        self.otp_layout.setContentsMargins(0,0,0,0)
        
        self.txt_otp = QLineEdit()
        self.txt_otp.setPlaceholderText("6자리 숫자")
        self.btn_verify = QPushButton("로그인 확인")
        self.btn_verify.clicked.connect(self.on_verify_sms)
        self.btn_cancel_wait = QPushButton("대기 취소")
        self.btn_cancel_wait.clicked.connect(self.on_cancel_otp_wait)
        self.btn_cancel_wait.setVisible(False)

        self.otp_layout.addWidget(self.txt_otp)
        self.otp_layout.addWidget(self.btn_verify)
        self.otp_layout.addWidget(self.btn_cancel_wait)
        self.otp_widget.setVisible(False)

        self.layout.addWidget(self.otp_widget)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.auto_sms_request_attempted:
            return
        self.auto_sms_request_attempted = True
        QTimer.singleShot(0, self.btn_request_sms.click)

    def closeEvent(self, event) -> None:
        self._stop_auto_otp_polling()
        super().closeEvent(event)

    def _set_auto_otp_status(self, text: str) -> None:
        self.lbl_auto_otp_status.setText(text)

    def _auto_otp_enabled(self) -> bool:
        return self.chk_auto_otp.isChecked() and bool(self.txt_bridge_url.text().strip())

    def _reset_login_view(self) -> None:
        self._stop_auto_otp_polling()
        self.txt_id.setEnabled(True)
        self.txt_pw.setEnabled(True)
        self.btn_request_sms.setVisible(True)
        self.btn_request_sms.setEnabled(True)
        self.btn_request_sms.setText("문자 인증번호 받기")
        self.txt_otp.clear()
        self.otp_widget.setVisible(False)
        self.btn_verify.setEnabled(True)
        self.btn_verify.setText("로그인 확인")
        self.btn_cancel_wait.setVisible(False)
        self.btn_cancel_wait.setEnabled(True)
        self._set_auto_otp_status("대기 중")

    def _show_otp_wait_view(self) -> None:
        self.txt_id.setEnabled(False)
        self.txt_pw.setEnabled(False)
        self.btn_request_sms.setVisible(False)
        self.txt_otp.clear()
        self.btn_verify.setEnabled(True)
        self.btn_verify.setText("로그인 확인")
        self.btn_cancel_wait.setEnabled(True)
        self.btn_cancel_wait.setVisible(True)
        self.otp_widget.setVisible(True)

    def _stop_auto_otp_polling(self) -> None:
        if self.otp_poll_start_timer.isActive():
            self.otp_poll_start_timer.stop()
        if self.otp_poll_start_countdown_timer.isActive():
            self.otp_poll_start_countdown_timer.stop()
        if self.otp_poll_timer.isActive():
            self.otp_poll_timer.stop()
        self.otp_poll_start_remaining_seconds = 0
        self.otp_auto_verify_in_progress = False

    def _set_otp_poll_start_countdown_status(self) -> None:
        self._set_auto_otp_status(f"{self.otp_poll_start_remaining_seconds}초 후 서버 확인 시작...")

    def _update_otp_poll_start_countdown(self) -> None:
        if self.otp_poll_start_remaining_seconds <= 1:
            self.otp_poll_start_countdown_timer.stop()
            return
        self.otp_poll_start_remaining_seconds -= 1
        self._set_otp_poll_start_countdown_status()

    def _schedule_auto_otp_polling(self) -> None:
        if not self._auto_otp_enabled():
            self._set_auto_otp_status("자동 수신 비활성화")
            return
        self._stop_auto_otp_polling()
        self.otp_poll_start_remaining_seconds = max(1, (self.otp_poll_start_delay_ms + 999) // 1000)
        self._set_otp_poll_start_countdown_status()
        self.otp_poll_start_countdown_timer.start()
        self.otp_poll_start_timer.start(self.otp_poll_start_delay_ms)

    def _start_auto_otp_polling(self) -> None:
        if not self._auto_otp_enabled():
            self._set_auto_otp_status("자동 수신 비활성화")
            return
        if self.otp_poll_start_countdown_timer.isActive():
            self.otp_poll_start_countdown_timer.stop()
        self.otp_poll_start_remaining_seconds = 0
        self.otp_poll_attempts = 0
        self.otp_auto_verify_in_progress = False
        self._set_auto_otp_status("인증번호 대기 중...")
        self.otp_poll_timer.start()

    def on_cancel_otp_wait(self) -> None:
        self._reset_login_view()

    def _poll_for_auto_otp(self) -> None:
        if self.otp_auto_verify_in_progress:
            return

        self.otp_poll_attempts += 1
        if self.otp_poll_attempts > self.otp_poll_limit:
            self._stop_auto_otp_polling()
            self._set_auto_otp_status("자동 수신 시간 초과, 수동 입력 필요")
            return

        bridge_url = self.txt_bridge_url.text().strip()
        if not bridge_url:
            self._stop_auto_otp_polling()
            self._set_auto_otp_status("중계 URL이 비어 있습니다")
            return

        client = OTPBridgeClient(bridge_url)
        result = client.fetch_latest_otp()
        if result.error:
            self._set_auto_otp_status(f"서버 확인 실패: {result.error}")
            return
        if not result.ok:
            self._set_auto_otp_status(f"인증번호 대기 중... ({self.otp_poll_attempts}/{self.otp_poll_limit})")
            return

        self._stop_auto_otp_polling()
        self.otp_auto_verify_in_progress = True
        self.txt_otp.setText(result.code)
        self._set_auto_otp_status(f"인증번호 수신: {result.code}")
        client.delete_otp()
        self.on_verify_sms(auto_triggered=True)

    def on_request_sms(self):
        user_id = self.txt_id.text().strip()
        pw = self.txt_pw.text()
        if not user_id or not pw:
            QMessageBox.warning(self, "경고", "아이디와 비밀번호를 입력해 주세요.")
            return

        try:
            os.makedirs(_state_dir(), exist_ok=True)
            with open(_erp_credentials_path(), "w", encoding="utf-8") as f:
                json.dump({"id": user_id, "pw": pw}, f)
        except Exception:
            pass

        self.btn_request_sms.setEnabled(False)
        self.btn_request_sms.setText("요청 중...")
        QApplication.processEvents()

        success = self.session.login_step1_request_sms(user_id, pw)
        if success:
            self._show_otp_wait_view()
            self._schedule_auto_otp_polling()
        else:
            QMessageBox.critical(self, "오류", "SMS 인증번호 발송에 실패했습니다.")
            self._reset_login_view()

    def on_verify_sms(self, auto_triggered: bool = False):
        otp = self.txt_otp.text().strip()
        if not otp:
            QMessageBox.warning(self, "경고", "인증번호를 입력해 주세요.")
            return

        self._stop_auto_otp_polling()
        self.btn_verify.setEnabled(False)
        self.btn_verify.setText("확인 중...")
        self.btn_cancel_wait.setEnabled(False)
        QApplication.processEvents()

        success = self.session.login_step2_verify_sms(otp)
        if success:
            self._set_auto_otp_status("로그인 완료")
            self.accept()
        else:
            if auto_triggered:
                self._set_auto_otp_status("자동 인증 실패, 수동 입력 필요")
            else:
                self._set_auto_otp_status("인증 실패, 다시 시도해 주세요")
            QMessageBox.critical(self, "오류", "인증번호 검증 또는 로그인에 실패했습니다.\n다시 시도해 주세요.")
            self.btn_verify.setEnabled(True)
            self.btn_verify.setText("로그인 확인")
            self.btn_cancel_wait.setEnabled(True)
            self.otp_auto_verify_in_progress = False


class ERPMultipleModelDialog(QDialog):
    def __init__(self, parent: QWidget, models: List[dict]):
        super().__init__(parent)
        self.setWindowTitle("ERP 모델 선택")
        self.resize(600, 300)
        self.selected_model: Optional[dict] = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("검색된 모델이 여러 개입니다. 정확한 모델을 선택해 주세요."))
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["모델명(ITEM_CD)", "모델 설명 (ITEM_DESC)", "분류 (CAT_LVL1)"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        
        self.table.setRowCount(len(models))
        for i, m in enumerate(models):
            self.table.setItem(i, 0, QTableWidgetItem(m.get("ITEM_CD", "")))
            self.table.setItem(i, 1, QTableWidgetItem(m.get("ITEM_DESC", "")))
            self.table.setItem(i, 2, QTableWidgetItem(m.get("CAT_LVL1_NM", "")))
            self.table.item(i, 0).setData(Qt.UserRole, m) # store the dict
            
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("선택 후 조회")
        self.btn_cancel = QPushButton("취소")
        
        self.btn_ok.clicked.connect(self.on_ok)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.table.itemDoubleClicked.connect(self.on_ok)
        
    def on_ok(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "선택 필요", "모델을 선택해 주세요.")
            return
            
        row = selected_items[0].row()
        self.selected_model = self.table.item(row, 0).data(Qt.UserRole)
        self.accept()

class InventoryMultipleResultDialog(QDialog):
    def __init__(self, parent: QWidget, results_text: str):
        super().__init__(parent)
        self.setWindowTitle("다중 모델 재고/생산계획 조회 결과")
        self.resize(700, 500)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        font = self.text_edit.font()
        font.setFamily("Consolas")
        self.text_edit.setFont(font)
        self.text_edit.setPlainText(results_text)
        
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)


class InventorySearchStatusDialog(QDialog):
    """모델 재고 조회 중 상태를 표시하는 작은 비모달 창."""

    def __init__(self, parent: QWidget, model_name: str):
        super().__init__(parent)
        self.setWindowTitle("ERP 조회 중")
        self.setWindowFlags(
            Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self.lbl_title = QLabel("⏳ ERP 재고 조회 중...")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.lbl_title)

        self.lbl_model = QLabel(f"입력 모델: {model_name}")
        self.lbl_model.setWordWrap(True)
        layout.addWidget(self.lbl_model)

        self.lbl_status = QLabel("모델 목록 검색 중...")
        self.lbl_status.setStyleSheet("color: #555; font-size: 11px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.setStyleSheet(
            "QDialog { background-color: #f0f8ff; border: 1px solid #93c5fd; border-radius: 8px; }"
        )

    def set_status(self, text: str) -> None:
        self.lbl_status.setText(text)
        QApplication.processEvents()

    def show_centered_on_parent(self) -> None:
        self.adjustSize()
        parent = self.parent()
        if parent:
            pg = parent.geometry()
            x = pg.x() + (pg.width() - self.width()) // 2
            y = pg.y() + (pg.height() - self.height()) // 2
            self.move(x, y)
        self.show()
        QApplication.processEvents()


@dataclass
class LoadedWorkbook:
    path: str
    temp_path: str
    wb: Any
    ws: Any
    tables: List[TableRegion]
    all_sheets_tables: Dict[str, List[TableRegion]]


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def _state_dir() -> str:
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return os.path.join(appdata, "PriceTableEditor")
    return os.path.join(os.path.expanduser("~"), APP_STATE_DIRNAME)


def _state_file_path() -> str:
    return os.path.join(_state_dir(), SESSION_STATE_FILENAME)


def _erp_credentials_path() -> str:
    return os.path.join(_state_dir(), "erp_credentials.json")


def _snapshot_file_path() -> str:
    return os.path.join(_state_dir(), SESSION_SNAPSHOT_FILENAME)


class RelatedModelsDialog(QDialog):
    def __init__(self, parent: QWidget, title_or_model: str, related_data: List[dict], multi_model: bool = False):
        super().__init__(parent)
        self.setWindowTitle(f"연관/중복 모델 수정 - {title_or_model}")
        self.resize(1000, 450)
        self.related_data = related_data
        
        layout = QVBoxLayout(self)
        
        if multi_model:
            info_label = QLabel("기획전 기준 모델명이 다른 탭에도 중복 존재하는 항목을 찾았습니다.\n수정할 항목을 선택하고 적용할 조정 할인율(%p)을 입력해 주세요.")
        else:
            info_label = QLabel(f"<b>{title_or_model}</b> 모델이 다른 탭에도 존재합니다.\n수정할 항목을 선택하고 조정할 할인율(%p)을 입력한 뒤 적용하세요.")
            
        layout.addWidget(info_label)
        
        self.table = QTableWidget()
        if multi_model:
            self.table.setColumnCount(9)
            self.table.setHorizontalHeaderLabels([
                "선택", "모델명", "시트명", "기획가공급가", "기획수정공급가",
                "기존공급가", "조정 할인율(%p)", "조정 후 공급가", "기획수정 공급가 차이%"
            ])
        else:
            self.table.setColumnCount(8)
            self.table.setHorizontalHeaderLabels([
                "선택", "시트명", "기획가공급가", "기획수정공급가",
                "기존공급가", "조정 할인율(%p)", "조정 후 공급가", "기획수정 공급가 차이%"
            ])

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        self.table.setRowCount(len(related_data))
        self.checkboxes: List[QCheckBox] = []
        self.spinboxes: List[QDoubleSpinBox] = []
        
        for i, data in enumerate(related_data):
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True) 
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0,0,0,0)
            self.table.setCellWidget(i, 0, chk_widget)
            self.checkboxes.append(chk)
            
            col_offset = 0
            if multi_model:
                self._set_item(i, 1, data.get("model_name", ""))
                col_offset = 1
                
            self._set_item(i, 1 + col_offset, data["sheet_name"])
            
            first_orig = data.get("first_orig_supply")
            first_mod = data.get("first_mod_supply")
            cur_supply = data["supply"]
            
            self._set_item(i, 2 + col_offset, "" if first_orig is None else f"{int(first_orig):,}")
            self._set_item(i, 3 + col_offset, "" if first_mod is None else f"{int(first_mod):,}")
            self._set_item(i, 4 + col_offset, "" if cur_supply is None else f"{int(cur_supply):,}")
            
            # Spinbox
            spin = QDoubleSpinBox()
            spin.setSuffix(" %p")
            spin.setDecimals(2)
            spin.setRange(-100.0, 100.0)
            spin.setSingleStep(0.5)
            spin.setValue(0.0)
            spin.setProperty("row_index", i) # Save row index for signal mapping
            spin.valueChanged.connect(self.on_spin_changed)
            self.table.setCellWidget(i, 5 + col_offset, spin)
            self.spinboxes.append(spin)
            
            # Placeholder for adjusted supply
            self._set_item(i, 6 + col_offset, "" if cur_supply is None else f"{int(cur_supply):,}")
            
            # Placeholder for supply diff %
            diff_text = ""
            if first_mod and cur_supply:
                diff_pct = ((cur_supply - first_mod) / first_mod) * 100
                diff_text = f"{diff_pct:.2f}%"
            self._set_item(i, 7 + col_offset, diff_text)

        # Batch apply section
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("일괄 적용 할인율(%p):"))
        self.batch_spin = QDoubleSpinBox()
        self.batch_spin.setSuffix(" %p")
        self.batch_spin.setDecimals(2)
        self.batch_spin.setRange(-100.0, 100.0)
        self.batch_spin.setSingleStep(0.5)
        batch_layout.addWidget(self.batch_spin)
        
        btn_batch = QPushButton("선택 항목 일괄 채우기")
        btn_batch.clicked.connect(self.on_batch_fill)
        batch_layout.addWidget(btn_batch)
        batch_layout.addStretch()
        layout.addLayout(batch_layout)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_apply = QPushButton("선택 항목 적용")
        btn_apply.clicked.connect(self.accept)
        btn_layout.addWidget(btn_apply)
        
        layout.addLayout(btn_layout)

    def _set_item(self, row, col, text):
        it = QTableWidgetItem(str(text))
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, col, it)
        
    def on_spin_changed(self, val: float):
        spin = self.sender()
        if not spin:
            return
        row = spin.property("row_index")
        if row is None:
            return
            
        data = self.related_data[row]
        msrp = data.get("msrp")
        if msrp is None:
            return
            
        from excel_price_tables import clamp_discount_ratio, recalc_supply_price, parse_discount_ratio
        
        disc = data.get("discount")
        old_ratio = parse_discount_ratio(disc)
        if old_ratio is None:
            old_ratio = 0.0
            
        delta_ratio = val / 100.0
        new_ratio = clamp_discount_ratio(old_ratio + delta_ratio)
        new_supply = recalc_supply_price(msrp, new_ratio)
        
        col_offset = 1 if self.table.columnCount() == 9 else 0
        self._set_item(row, 6 + col_offset, f"{int(new_supply):,}")
        
        # Calculate dynamic supply diff %
        first_mod = data.get("first_mod_supply")
        diff_text = ""
        if first_mod and new_supply:
            diff_pct = ((new_supply - first_mod) / first_mod) * 100
            diff_text = f"{diff_pct:.2f}%"
        self._set_item(row, 7 + col_offset, diff_text)

    def on_batch_fill(self):
        val = self.batch_spin.value()
        for i, chk in enumerate(self.checkboxes):
            if chk.isChecked():
                self.spinboxes[i].setValue(val)

                
    def get_selected_adjustments(self) -> List[dict]:
        results = []
        for i, chk in enumerate(self.checkboxes):
            if chk.isChecked():
                results.append({
                    "data": self.related_data[i],
                    "delta": self.spinboxes[i].value()
                })
        return results


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("엑셀 가격표 할인율 조정기")
        self.resize(980, 640)

        self.loaded: Optional[LoadedWorkbook] = None
        self.table_deltas_pp: Dict[int, float] = {}
        self._last_temp_path: Optional[str] = None
        self.session_opened_at: Optional[str] = None
        self.last_batch_delta_pp: Optional[float] = None
        # (table_index, row_index) -> ?먮옒 怨듦툒媛
        self.original_supply: Dict[Tuple[int, int], float] = {}
        
        # ERP ?몄뀡 諛??대씪?댁뼵???몄뒪?댁뒪
        self.erp_session = ERPSession()
        self.erp_client = ERPClient(self.erp_session)
        self.inventory_queue = InventoryQueueController()

        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)

        # ?곷떒: ?뚯씪 濡쒕뱶
        file_bar = QHBoxLayout()
        self.btn_open = QPushButton("엑셀 파일 열기(.xlsx)")
        self.lbl_file = QLabel("파일을 선택해 주세요")
        self.lbl_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        file_bar.addWidget(self.btn_open)
        file_bar.addWidget(self.lbl_file, 1)
        layout.addLayout(file_bar)

        self.lbl_session_info = QLabel("이전 기록이 없습니다.")
        self.lbl_session_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_session_info)

        splitter = QSplitter()
        layout.addWidget(splitter, 1)

        # 醫뚯륫: ?뚯씠釉?紐⑸줉
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("감지된 테이블"))
        self.list_tables = QListWidget()
        left_layout.addWidget(self.list_tables, 1)

        self.grp_inventory_search = QGroupBox("개별 모델 재고 조회")
        inv_search_layout = QHBoxLayout(self.grp_inventory_search)
        self.txt_manual_model = QLineEdit()
        self.txt_manual_model.setPlaceholderText("모델명 입력")
        self.btn_manual_search = QPushButton("조회")
        inv_search_layout.addWidget(self.txt_manual_model)
        inv_search_layout.addWidget(self.btn_manual_search)
        left_layout.addWidget(self.grp_inventory_search)

        splitter.addWidget(left)

        # ?곗륫: ?좏깮???뚯씠釉??몄쭛
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.grp_edit = QGroupBox("테이블 할인율 조정")
        form = QFormLayout(self.grp_edit)

        self.lbl_table_info = QLabel("-")
        self.lbl_table_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("선택 테이블", self.lbl_table_info)

        self.spin_delta = QDoubleSpinBox()
        self.spin_delta.setSuffix(" %p")
        self.spin_delta.setDecimals(2)
        self.spin_delta.setRange(-100.0, 100.0)
        self.spin_delta.setSingleStep(0.5)
        form.addRow("할인율 조정", self.spin_delta)

        self.btn_apply = QPushButton("이 테이블에 적용")
        self.btn_apply_all = QPushButton("모든 테이블에 적용")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_apply_all)
        form.addRow(btn_row)

        right_layout.addWidget(self.grp_edit)

        self.grp_preview = QGroupBox("테이블 내용 미리보기")
        prev_layout = QVBoxLayout(self.grp_preview)
        self.tbl_preview = QTableWidget()
        # 모델명 | 출하가 | 기존 공급가 | 차액 | 공급가 | 할인율
        self.tbl_preview.setColumnCount(6)
        self.tbl_preview.setHorizontalHeaderLabels(
            ["모델명", "출하가", "기존 공급가", "차액", "공급가", "할인율 DC율"]
        )
        self.tbl_preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_preview.setAlternatingRowColors(True)
        prev_layout.addWidget(self.tbl_preview, 1)
        
        self.btn_search_related = QPushButton("선택 모델 연관 시트 검색 및 수정")
        prev_layout.addWidget(self.btn_search_related)

        self.btn_search_all_duplicates = QPushButton("다른 탭 중복상품 전체 검색 및 일괄 수정")
        prev_layout.addWidget(self.btn_search_all_duplicates)

        self.btn_erp_check_row = QPushButton("선택 행 ERP 개별 조회 (재고/생산계획)")
        self.btn_erp_check_row.setStyleSheet("background-color: #e0f0ff; font-weight: bold;")
        prev_layout.addWidget(self.btn_erp_check_row)

        right_layout.addWidget(self.grp_preview, 1)

        self.grp_save = QGroupBox("저장 및 연동")
        save_form = QFormLayout(self.grp_save)
        self.txt_save_name = QLineEdit()
        self.txt_save_name.setPlaceholderText("예: 결과_가격표.xlsx")
        save_form.addRow("저장 파일명", self.txt_save_name)
        
        self.btn_save = QPushButton("엑셀 저장")
        self.btn_compare = QPushButton("가격 비교(다나와)")
        
        self.btn_erp_login = QPushButton("ERP 로그인")
        self.lbl_erp_status = QLabel("미로그인 상태")
        self.lbl_erp_status.setStyleSheet("color: red; font-weight: bold;")
        
        save_btn_row = QHBoxLayout()
        save_btn_row.addWidget(self.btn_save)
        save_btn_row.addWidget(self.btn_compare)
        save_form.addRow(save_btn_row)
        
        erp_row = QHBoxLayout()
        erp_row.addWidget(self.btn_erp_login)
        erp_row.addWidget(self.lbl_erp_status)
        self.lbl_erp_keepalive = QLabel("")
        self.lbl_erp_keepalive.setStyleSheet("color: #555; font-size: 10px;")
        erp_row.addWidget(self.lbl_erp_keepalive)
        erp_row.addStretch()
        save_form.addRow("ERP 상태", erp_row)
        
        right_layout.addWidget(self.grp_save)
        right_layout.addStretch(1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self.grp_inventory_queue = QGroupBox("카카오 재고 큐 상태")
        queue_layout = QVBoxLayout(self.grp_inventory_queue)
        queue_form = QFormLayout()

        self.lbl_inventory_bridge_url = QLabel(DEFAULT_INVENTORY_BRIDGE_BASE_URL or "-")
        self.lbl_inventory_bridge_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_inventory_bridge_status = QLabel("연결 확인 중")
        self.lbl_inventory_erp_status = QLabel("ERP 로그인 필요")
        self.lbl_inventory_queue_stats = QLabel("-")
        self.lbl_inventory_worker_status = QLabel("대기 중")
        self.lbl_inventory_worker_status.setWordWrap(True)

        queue_form.addRow("브리지 URL", self.lbl_inventory_bridge_url)
        queue_form.addRow("브리지 상태", self.lbl_inventory_bridge_status)
        queue_form.addRow("ERP 준비", self.lbl_inventory_erp_status)
        queue_form.addRow("큐 현황", self.lbl_inventory_queue_stats)
        queue_form.addRow("작업 상태", self.lbl_inventory_worker_status)
        queue_layout.addLayout(queue_form)

        self.list_inventory_events = QListWidget()
        self.list_inventory_events.setMaximumHeight(120)
        queue_layout.addWidget(self.list_inventory_events)
        layout.addWidget(self.grp_inventory_queue)

        self._set_enabled(False)

        # signals
        self.btn_open.clicked.connect(self.on_open)
        self.list_tables.currentItemChanged.connect(self.on_table_selected)
        self.btn_apply.clicked.connect(self.on_apply_discount)
        self.btn_apply_all.clicked.connect(self.on_apply_discount_all)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_compare.clicked.connect(self.on_compare_prices)
        self.tbl_preview.itemSelectionChanged.connect(self.on_preview_selection_changed)
        self.btn_search_related.clicked.connect(self.on_search_related)
        self.btn_search_all_duplicates.clicked.connect(self.on_search_all_duplicates)
        self.btn_erp_check_row.clicked.connect(self.on_erp_check_row)
        self.btn_manual_search.clicked.connect(self.on_manual_inventory_search)
        self.btn_erp_login.clicked.connect(self.on_erp_login)
        self.txt_save_name.textChanged.connect(self._persist_session_metadata_only)

        self.inventory_status_timer = QTimer(self)
        self.inventory_status_timer.setInterval(1000)
        self.inventory_status_timer.timeout.connect(self._refresh_inventory_queue_status)
        self.inventory_status_timer.start()

        # ERP 세션 keep-alive 타이머: 60초마다 만료 여부 점검, 필요 시 keep_alive() 호출
        self.ERP_KEEPALIVE_INTERVAL_SEC = 15 * 60  # 15분
        self.erp_keepalive_timer = QTimer(self)
        self.erp_keepalive_timer.setInterval(60 * 1000)  # 60초마다 점검
        self.erp_keepalive_timer.timeout.connect(self._check_erp_keepalive)
        self.erp_keepalive_timer.start()

        self.inventory_queue.start()
        self._sync_inventory_queue_session()
        self._sync_inventory_queue_workbook_prices()
        self._refresh_inventory_queue_status()

        self._restore_last_session()

        restart_count = 0
        for a in sys.argv:
            if a.startswith("--restart-count="):
                try:
                    restart_count = int(a.split("=", 1)[1])
                except ValueError:
                    pass
        if restart_count > 0:
            self.lbl_erp_keepalive.setText(f"(자동 재시작 {restart_count}회)")
            self.lbl_erp_keepalive.setStyleSheet("color: #b07000; font-size: 10px;")

        if "--auto-login" in sys.argv:
            QTimer.singleShot(500, self.on_erp_login)

    def _set_enabled(self, enabled: bool) -> None:
        self.list_tables.setEnabled(enabled)
        self.grp_edit.setEnabled(enabled)
        self.grp_preview.setEnabled(enabled)
        self.grp_save.setEnabled(enabled)
        self.btn_apply.setEnabled(enabled)
        if hasattr(self, "btn_apply_all"):
            self.btn_apply_all.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        if hasattr(self, "btn_compare"):
            self.btn_compare.setEnabled(enabled)
        if hasattr(self, "btn_search_related"):
            self.btn_search_related.setEnabled(False)  # ???좏깮 ???쒖꽦?붾맖
        if hasattr(self, "btn_search_all_duplicates"):
            self.btn_search_all_duplicates.setEnabled(enabled)

    def _format_session_info(self) -> str:
        if not self.session_opened_at:
            return "이전 기록이 없습니다."

        try:
            dt = datetime.fromisoformat(self.session_opened_at)
            opened_text = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            opened_text = self.session_opened_at

        if self.last_batch_delta_pp is None:
            batch_text = "없음"
        else:
            batch_text = f"{self.last_batch_delta_pp:+.2f}%p"

        return f"이전 작업 일시: {opened_text} | 일괄 조정 할인율: {batch_text}"

    def _update_session_info_label(self) -> None:
        self.lbl_session_info.setText(self._format_session_info())

    def _sync_inventory_queue_session(self) -> None:
        if self.erp_session.is_session_valid():
            self.inventory_queue.sync_erp_session(self.erp_session)
        else:
            self.inventory_queue.sync_erp_session(None)

    def _inventory_model_aliases(self, model_name: str) -> List[str]:
        aliases: List[str] = []
        seen: set[str] = set()
        raw = (model_name or "").strip().upper()
        if not raw:
            return aliases

        for candidate in (raw, raw.split(".", 1)[0], raw.split("-", 1)[0], raw.split(" ", 1)[0]):
            normalized = re.sub(r"[^A-Z0-9]", "", candidate)
            if len(normalized) < 5 or normalized in seen:
                continue
            seen.add(normalized)
            aliases.append(normalized)
        return aliases

    def _build_inventory_workbook_price_index(self) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}
        if not self.loaded:
            return index

        for sheet_name, tables in self.loaded.all_sheets_tables.items():
            sheet_obj = self.loaded.wb[sheet_name]
            for table in tables:
                for row in range(table.first_data_row, table.last_data_row + 1):
                    model_value = sheet_obj.cell(row=row, column=table.col_model).value
                    if not isinstance(model_value, str) or not model_value.strip():
                        continue

                    supply_value = sheet_obj.cell(row=row, column=table.col_supply).value
                    supply_price: Optional[int] = None
                    if isinstance(supply_value, (int, float)):
                        supply_price = int(float(supply_value))
                    else:
                        try:
                            if supply_value is not None and str(supply_value).strip():
                                supply_price = int(float(str(supply_value).replace(",", "")))
                        except ValueError:
                            supply_price = None

                    if supply_price is None:
                        continue

                    entry = {
                        "model_name": model_value.strip(),
                        "sheet_name": sheet_name,
                        "supply_price": supply_price,
                    }
                    for alias in self._inventory_model_aliases(model_value):
                        index.setdefault(alias, entry)

        return index

    def _sync_inventory_queue_workbook_prices(self) -> None:
        self.inventory_queue.sync_workbook_price_index(self._build_inventory_workbook_price_index())

    def _format_single_model_block(self, lookup: InventoryLookupResult, label: str = "") -> List[str]:
        item_cd = str(lookup.model.get("ITEM_CD", "")).strip()
        item_desc = str(lookup.model.get("ITEM_DESC", "")).strip()

        header = f"[{label}] {item_cd}" if label else f"모델명: {item_cd}"
        lines = [header]
        if item_desc:
            lines.append(f"  설명: {item_desc}")

        inventory_parts: List[str] = []
        for inv in lookup.inventory_rows:
            org = str(inv.get("INVENTORY_ORG_NAME", "")).strip() or "창고"
            qty = self.erp_client._to_int(inv.get("AVAILABLE_QTY"))
            if qty > 0:
                inventory_parts.append(f"  - {org}: {qty}개")

        if lookup.inventory_error and not lookup.inventory_rows:
            lines.append(f"  재고 조회 실패: {lookup.inventory_error}")
        else:
            lines.append(f"  재고 합계: {lookup.inventory_total}개")
            lines.extend(inventory_parts if inventory_parts else ["  - 가용 재고 없음"])

        if lookup.production_error:
            lines.append(f"  생산계획 조회 참고: {lookup.production_error}")
        else:
            if lookup.production_plan.days:
                lines.append("  생산계획:")
                for detail_line in format_production_plan_details(lookup.production_plan):
                    lines.append(f"    - {detail_line}")
            else:
                lines.append("  생산계획: 표시할 수량이 있는 날짜가 없습니다")

        return lines

    def _format_inventory_lookup_text(self, lookup: InventoryLookupResult) -> str:
        lines: List[str] = []

        if lookup.selection_note:
            lines.append(lookup.selection_note)
            lines.append("")

        if lookup.paired_results:
            # 세트 구성: 각 모델을 번호로 구분해 표시
            all_items = (lookup,) + lookup.paired_results
            for idx, item in enumerate(all_items, start=1):
                lines.extend(self._format_single_model_block(item, label=f"구성 {idx}"))
                lines.append("")
            # 세트 합계
            total_inv = sum(r.inventory_total for r in all_items)
            lines.append(f"세트 재고 합계: {total_inv}개")
        else:
            lines.extend(self._format_single_model_block(lookup))

        return "\n".join(lines)

    def _refresh_inventory_queue_status(self) -> None:
        snapshot = self.inventory_queue.snapshot()
        self.lbl_inventory_bridge_url.setText(snapshot.bridge_url or "-")

        last_poll_text = "-"
        if snapshot.last_poll_at:
            last_poll_text = datetime.fromtimestamp(snapshot.last_poll_at).strftime("%H:%M:%S")

        if snapshot.bridge_ok:
            bridge_text = f"정상 (마지막 성공 {last_poll_text}, {snapshot.poll_interval_seconds:.1f}초 간격)"
        elif snapshot.last_poll_at:
            bridge_text = f"오류 (마지막 시도 {last_poll_text})"
        else:
            bridge_text = "연결 확인 중"
        if snapshot.last_error:
            bridge_text += f" | {snapshot.last_error}"
        self.lbl_inventory_bridge_status.setText(bridge_text)

        if snapshot.erp_ready:
            self.lbl_inventory_erp_status.setText("준비됨")
            self.lbl_inventory_erp_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_inventory_erp_status.setText("ERP 로그인 필요")
            self.lbl_inventory_erp_status.setStyleSheet("color: red; font-weight: bold;")

        self.lbl_inventory_queue_stats.setText(
            f"원격 WAIT {snapshot.remote_waiting_count}건 | 로컬 대기 {snapshot.queued_count}건 | "
            f"처리중 {snapshot.inflight_count}건 | 완료 {snapshot.completed_count}건 | 실패 {snapshot.failed_count}건"
        )
        self.lbl_inventory_worker_status.setText(f"{snapshot.worker_status} | {snapshot.current_job_text}")

        current_items = [self.list_inventory_events.item(i).text() for i in range(self.list_inventory_events.count())]
        if current_items != snapshot.recent_events:
            self.list_inventory_events.clear()
            self.list_inventory_events.addItems(snapshot.recent_events)

    def _ensure_state_dir(self) -> None:
        os.makedirs(_state_dir(), exist_ok=True)

    def _serialize_original_supply(self) -> Dict[str, float]:
        return {
            f"{table_index}:{row_index}": value
            for (table_index, row_index), value in self.original_supply.items()
        }

    def _deserialize_original_supply(self, data: Dict[str, Any]) -> Dict[Tuple[int, int], float]:
        result: Dict[Tuple[int, int], float] = {}
        for key, value in data.items():
            try:
                table_index_str, row_index_str = key.split(":", 1)
                result[(int(table_index_str), int(row_index_str))] = float(value)
            except (ValueError, TypeError):
                continue
        return result

    def _current_state_payload(self) -> Optional[Dict[str, Any]]:
        if not self.loaded:
            return None

        selected_table = self._get_selected_table()
        return {
            "version": 1,
            "path": self.loaded.path,
            "opened_at": self.session_opened_at,
            "last_batch_delta_pp": self.last_batch_delta_pp,
            "selected_table_index": selected_table.index if selected_table else None,
            "table_deltas_pp": {str(k): v for k, v in self.table_deltas_pp.items()},
            "original_supply": self._serialize_original_supply(),
            "save_name": self.txt_save_name.text().strip(),
        }

    def _write_state_file(self, payload: Dict[str, Any]) -> None:
        self._ensure_state_dir()
        with open(_state_file_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _persist_session_metadata_only(self, *_args: Any) -> None:
        payload = self._current_state_payload()
        if not payload:
            return
        try:
            self._write_state_file(payload)
        except OSError:
            pass

    def _persist_session_state(self) -> None:
        payload = self._current_state_payload()
        if not payload or not self.loaded:
            self._sync_inventory_queue_workbook_prices()
            return

        self._sync_inventory_queue_workbook_prices()
        try:
            self._ensure_state_dir()
            self.loaded.wb.save(_snapshot_file_path())
            self._write_state_file(payload)
        except OSError:
            pass

    def _clear_last_session_state(self) -> None:
        for path in (_state_file_path(), _snapshot_file_path()):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _load_workbook_state(
        self,
        *,
        path: str,
        temp_source_path: str,
        opened_at: Optional[str],
        original_supply: Optional[Dict[Tuple[int, int], float]] = None,
        table_deltas_pp: Optional[Dict[int, float]] = None,
        selected_table_index: Optional[int] = None,
        save_name: Optional[str] = None,
        last_batch_delta_pp: Optional[float] = None,
    ) -> None:
        if self._last_temp_path and os.path.exists(self._last_temp_path):
            try:
                os.remove(self._last_temp_path)
            except OSError:
                pass

        fd, tmp = tempfile.mkstemp(prefix="price_table_", suffix=".xlsx")
        os.close(fd)
        shutil.copy2(temp_source_path, tmp)
        self._last_temp_path = tmp

        wb = load_workbook(tmp)
        ws = wb.worksheets[0]
        tables = detect_price_tables(ws)

        all_sheets_tables: Dict[str, List[TableRegion]] = {}
        for sheet in wb.worksheets:
            all_sheets_tables[sheet.title] = detect_price_tables(sheet)

        self.loaded = LoadedWorkbook(
            path=path,
            temp_path=tmp,
            wb=wb,
            ws=ws,
            tables=tables,
            all_sheets_tables=all_sheets_tables,
        )
        self.session_opened_at = opened_at
        self.last_batch_delta_pp = last_batch_delta_pp
        self.table_deltas_pp = {}
        self.original_supply = original_supply or {}

        self.lbl_file.setText(path)
        self.list_tables.clear()
        self.tbl_preview.setRowCount(0)
        self._update_session_info_label()

        if not tables:
            self._set_enabled(False)
            self._sync_inventory_queue_workbook_prices()
            return

        for t in tables:
            self.table_deltas_pp[t.index] = 0.0
            title = t.name.strip() if t.name.strip() else f"테이블 {t.index}"
            item = QListWidgetItem(f"{title}  (행 {t.header_row}~{t.last_data_row}, {t.n_rows}개)")
            item.setData(Qt.UserRole, t.index)
            self.list_tables.addItem(item)

            if original_supply is not None:
                continue

            for r in range(t.first_data_row, t.last_data_row + 1):
                val = ws.cell(row=r, column=t.col_supply).value
                if isinstance(val, (int, float)):
                    self.original_supply[(t.index, r)] = float(val)
                else:
                    try:
                        if val is not None and str(val).strip():
                            self.original_supply[(t.index, r)] = float(str(val).replace(",", ""))
                    except ValueError:
                        continue

        if table_deltas_pp:
            for k, v in table_deltas_pp.items():
                if k in self.table_deltas_pp:
                    self.table_deltas_pp[k] = v

        self._set_enabled(True)

        row_to_select = 0
        if selected_table_index is not None:
            for i in range(self.list_tables.count()):
                item = self.list_tables.item(i)
                if item and item.data(Qt.UserRole) == selected_table_index:
                    row_to_select = i
                    break
        self.list_tables.setCurrentRow(row_to_select)

        if save_name:
            self.txt_save_name.blockSignals(True)
            self.txt_save_name.setText(save_name)
            self.txt_save_name.blockSignals(False)
        else:
            base = os.path.basename(path)
            root, ext = os.path.splitext(base)
            self.txt_save_name.blockSignals(True)
            self.txt_save_name.setText(f"{root}_할인조정{ext or '.xlsx'}")
            self.txt_save_name.blockSignals(False)

        self._sync_inventory_queue_workbook_prices()

    def _restore_last_session(self) -> None:
        state_path = _state_file_path()
        snapshot_path = _snapshot_file_path()
        if not (os.path.exists(state_path) and os.path.exists(snapshot_path)):
            self._update_session_info_label()
            return

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            table_deltas_pp = {
                int(k): float(v) for k, v in (state.get("table_deltas_pp") or {}).items()
            }
            original_supply = self._deserialize_original_supply(state.get("original_supply") or {})

            self._load_workbook_state(
                path=state.get("path") or snapshot_path,
                temp_source_path=snapshot_path,
                opened_at=state.get("opened_at"),
                original_supply=original_supply,
                table_deltas_pp=table_deltas_pp,
                selected_table_index=state.get("selected_table_index"),
                save_name=state.get("save_name"),
                last_batch_delta_pp=state.get("last_batch_delta_pp"),
            )
        except Exception:
            self._clear_last_session_state()
            self._update_session_info_label()

    def on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "엑셀 파일 선택", "", "Excel (*.xlsx)")
        if not path:
            return

        try:
            opened_at = datetime.now().isoformat(timespec="seconds")
            self._load_workbook_state(
                path=path,
                temp_source_path=path,
                opened_at=opened_at,
                original_supply=None,
                table_deltas_pp=None,
                selected_table_index=1,
                save_name=None,
                last_batch_delta_pp=None,
            )
        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀을 여는 중 오류가 발생했습니다.\n\n{e}")
            return

        if not self.loaded or not self.loaded.tables:
            QMessageBox.warning(self, "테이블 없음", "첫 번째 시트에서 가격표 테이블을 찾지 못했습니다.\n(헤더: 모델명/출하가/공급가/할인율)")
            return

        self._persist_session_state()

    def _get_selected_table(self) -> Optional[TableRegion]:
        if not self.loaded:
            return None
        item = self.list_tables.currentItem()
        if not item:
            return None
        idx = item.data(Qt.UserRole)
        for t in self.loaded.tables:
            if t.index == idx:
                return t
        return None

    def on_table_selected(self) -> None:
        table = self._get_selected_table()
        if not table or not self.loaded:
            self.lbl_table_info.setText("-")
            self.tbl_preview.setRowCount(0)
            return

        self.lbl_table_info.setText(
            f"{table.name} | 헤더 행 {table.header_row} | 데이터 {table.first_data_row}~{table.last_data_row}"
        )
        delta = self.table_deltas_pp.get(table.index, 0.0)
        self.spin_delta.blockSignals(True)
        self.spin_delta.setValue(delta)
        self.spin_delta.blockSignals(False)

        self._fill_preview(table)
        self._persist_session_metadata_only()

    def _fill_preview(self, table: TableRegion) -> None:
        if not self.loaded:
            return
        ws = self.loaded.ws

        rows: List[Tuple[int, object, object, object, object]] = []
        for r in range(table.first_data_row, table.last_data_row + 1):
            model = ws.cell(row=r, column=table.col_model).value
            msrp = ws.cell(row=r, column=table.col_msrp).value
            supply = ws.cell(row=r, column=table.col_supply).value
            disc = ws.cell(row=r, column=table.col_discount).value

            # ?곗씠?곌? ?꾨땶 ?됱? ?쒖쇅
            if (model is None or (isinstance(model, str) and model.strip() == "")) and msrp is None:
                continue
            rows.append((r, model, msrp, supply, disc))

        self.tbl_preview.setRowCount(len(rows))
        for i, (row_idx, model, msrp, supply, disc) in enumerate(rows):
            # 紐⑤뜽紐? 異쒗븯媛
            self.tbl_preview.setItem(i, 0, QTableWidgetItem("" if model is None else str(model)))
            self.tbl_preview.setItem(i, 1, QTableWidgetItem("" if msrp is None else str(msrp)))

            # 湲곗〈 怨듦툒媛
            orig = self.original_supply.get((table.index, row_idx))
            orig_text = "" if orig is None else f"{int(orig):,}"
            self.tbl_preview.setItem(i, 2, QTableWidgetItem(orig_text))

            # ?꾩옱 怨듦툒媛 諛?李⑥븸
            cur_num: Optional[float] = None
            if isinstance(supply, (int, float)):
                cur_num = float(supply)
            else:
                try:
                    if supply is not None and str(supply).strip():
                        cur_num = float(str(supply).replace(",", ""))
                except ValueError:
                    cur_num = None

            diff_text = ""
            supply_text = "" if supply is None else str(supply)
            if orig is not None and cur_num is not None:
                diff = cur_num - orig
                sign = "+" if diff > 0 else ""
                diff_text = f"{sign}{int(diff):,}"
                supply_text = f"{int(cur_num):,}"

            self.tbl_preview.setItem(i, 3, QTableWidgetItem(diff_text))
            self.tbl_preview.setItem(i, 4, QTableWidgetItem(supply_text))
            ratio = parse_discount_ratio(disc)
            if ratio is None:
                disc_text = "" if disc is None else str(disc)
            else:
                disc_text = f"{ratio * 100:.2f}%"
            self.tbl_preview.setItem(i, 5, QTableWidgetItem(disc_text))
        self.tbl_preview.resizeColumnsToContents()

    def on_preview_selection_changed(self) -> None:
        has_selection = len(self.tbl_preview.selectedItems()) > 0
        if hasattr(self, "btn_search_related"):
            self.btn_search_related.setEnabled(has_selection)

    def on_search_related(self) -> None:
        if not self.loaded:
            return
            
        selected = self.tbl_preview.selectedItems()
        if not selected:
            return
            
        row = selected[0].row()
        model_item = self.tbl_preview.item(row, 0)
        if not model_item:
            return
            
        model_name = model_item.text().strip()
        if not model_name:
            QMessageBox.information(self, "알림", "선택한 행에 모델명이 없습니다.")
            return

        cur_sheet_name = self.loaded.ws.title

        # ?ㅻⅨ ??뱾?먯꽌 ?숈씪 紐⑤뜽紐?李얘린
        related_data = []
        for sheet_name, tables in self.loaded.all_sheets_tables.items():
            if sheet_name == cur_sheet_name:
                continue

            sheet_obj = self.loaded.wb[sheet_name]
            
            for t in tables:
                for r in range(t.first_data_row, t.last_data_row + 1):
                    val = sheet_obj.cell(row=r, column=t.col_model).value
                    if isinstance(val, str) and val.strip() == model_name:
                        supply = sheet_obj.cell(row=r, column=t.col_supply).value
                        if isinstance(supply, (int, float)):
                            supply = float(supply)
                        else:
                            try:
                                supply = float(str(supply).replace(",", "")) if supply is not None and str(supply).strip() else None
                            except ValueError:
                                supply = None
                                
                        disc = sheet_obj.cell(row=r, column=t.col_discount).value
                        
                        related_data.append({
                            "sheet_name": sheet_name,
                            "table_name": t.name,
                            "supply": supply,
                            "discount": disc,
                            "table": t,
                            "row": r,
                            "sheet_obj": sheet_obj
                        })
                        
        if not related_data:
            QMessageBox.information(self, "결과 없음", f"'{model_name}' 모델이 다른 탭에 존재하지 않습니다.")
            return
            
        # ?ㅼ씠?쇰줈洹??쒖떆
        dlg = RelatedModelsDialog(self, model_name, related_data)
        if dlg.exec() == QDialog.Accepted:
            adjustments = dlg.get_selected_adjustments()
            if not adjustments:
                return
                
            updated = 0
            for adj in adjustments:
                data = adj["data"]
                delta = adj["delta"]
                
                sheet_obj = data["sheet_obj"]
                table = data["table"]
                r = data["row"]
                
                if apply_discount_delta_to_row(sheet_obj, table, r, delta):
                    updated += 1
            self.last_batch_delta_pp = None
            self._update_session_info_label()
            self._persist_session_state()
            QMessageBox.information(self, "완료", f"총 {updated}개의 연관 모델 항목에 할인율 조정을 적용했습니다.\n(주의: 변경사항은 현재 시트가 아닌 다른 시트에도 적용되었습니다. 저장 버튼을 눌러 주세요.)")

    def on_search_all_duplicates(self) -> None:
        if not self.loaded:
            return

        cur_sheet_name = self.loaded.ws.title
        cur_tables = self.loaded.all_sheets_tables.get(cur_sheet_name, [])

        if not cur_tables:
            QMessageBox.information(self, "알림", "현재 시트에 테이블이 없습니다.")
            return

        # ?꾩옱 ??쓽 紐⑤뱺 紐⑤뜽 ?뱀꽦媛?(湲고쉷?꾧났湲됯?, 湲고쉷?꾩닔?뺥븷 怨듦툒媛 ?? ?섏쭛
        all_models_data = {}
        for t in cur_tables:
            for r in range(t.first_data_row, t.last_data_row + 1):
                val = self.loaded.ws.cell(row=r, column=t.col_model).value
                if isinstance(val, str) and val.strip():
                    m_name = val.strip()
                    
                    # MSRP (異쒗븯媛)
                    msrp_v = self.loaded.ws.cell(row=r, column=t.col_msrp).value
                    msrp = None
                    if isinstance(msrp_v, (int, float)):
                        msrp = float(msrp_v)
                    else:
                        try:
                            msrp = float(str(msrp_v).replace(",", "")) if msrp_v is not None and str(msrp_v).strip() else None
                        except ValueError:
                            pass
                            
                    # 湲고쉷?꾩닔?뺥븷 怨듦툒媛 (?꾩옱 ? 媛?
                    mod_v = self.loaded.ws.cell(row=r, column=t.col_supply).value
                    mod_supply = None
                    if isinstance(mod_v, (int, float)):
                        mod_supply = float(mod_v)
                    else:
                        try:
                            mod_supply = float(str(mod_v).replace(",", "")) if mod_v is not None and str(mod_v).strip() else None
                        except ValueError:
                            pass
                            
                    # 湲고쉷???먮낯 怨듦툒媛 (original_supply ?뺤뀛?덈━ 李멸퀬)
                    orig_supply = self.original_supply.get((t.index, r))
                    if orig_supply is None:
                        orig_supply = mod_supply # ?먮낯???놁쑝硫??꾩옱媛믪쓣 ?먮낯?쇰줈 媛꾩＜
                        
                    if m_name not in all_models_data: # 泥ル쾲吏?諛쒓껄??寃껊쭔 ?ъ슜
                        all_models_data[m_name] = {
                            "first_orig_supply": orig_supply,
                            "first_mod_supply": mod_supply,
                            "msrp": msrp
                        }

        if not all_models_data:
            QMessageBox.information(self, "알림", "현재 시트에서 모델명을 찾을 수 없습니다.")
            return

        # ?ㅻⅨ ??寃??        related_data = []
        for sheet_name, tables in self.loaded.all_sheets_tables.items():
            if sheet_name == cur_sheet_name:
                continue

            sheet_obj = self.loaded.wb[sheet_name]
            for t in tables:
                for r in range(t.first_data_row, t.last_data_row + 1):
                    val = sheet_obj.cell(row=r, column=t.col_model).value
                    if isinstance(val, str) and val.strip() in all_models_data:
                        model_name = val.strip()
                        
                        target_msrp = sheet_obj.cell(row=r, column=t.col_msrp).value
                        if isinstance(target_msrp, (int, float)):
                            target_msrp = float(target_msrp)
                        else:
                            try:
                                target_msrp = float(str(target_msrp).replace(",", "")) if target_msrp is not None and str(target_msrp).strip() else None
                            except ValueError:
                                target_msrp = None
                                
                        supply = sheet_obj.cell(row=r, column=t.col_supply).value
                        if isinstance(supply, (int, float)):
                            supply = float(supply)
                        else:
                            try:
                                supply = float(str(supply).replace(",", "")) if supply is not None and str(supply).strip() else None
                            except ValueError:
                                supply = None

                        disc = sheet_obj.cell(row=r, column=t.col_discount).value
                        first_data = all_models_data[model_name]
                        
                        related_data.append({
                            "model_name": model_name,  # ?ㅼ쨷 紐⑤뜽 援щ텇???꾪빐 異붽?
                            "sheet_name": sheet_name,
                            "table_name": t.name,
                            "first_orig_supply": first_data["first_orig_supply"],
                            "first_mod_supply": first_data["first_mod_supply"],
                            "msrp": target_msrp if target_msrp is not None else first_data["msrp"],
                            "supply": supply,
                            "discount": disc,
                            "table": t,
                            "row": r,
                            "sheet_obj": sheet_obj
                        })

        if not related_data:
            QMessageBox.information(self, "결과 없음", "다른 탭에 중복되는 모델을 찾지 못했습니다.")
            return

        # 湲곗〈 RelatedModelsDialog ?ъ궗??(??댄? 蹂寃?
        dlg = RelatedModelsDialog(self, "전체 중복 상품", related_data, multi_model=True)
        if dlg.exec() == QDialog.Accepted:
            adjustments = dlg.get_selected_adjustments()
            if not adjustments:
                return
                
            updated = 0
            for adj in adjustments:
                data = adj["data"]
                delta = adj["delta"]
                
                sheet_obj = data["sheet_obj"]
                table = data["table"]
                r = data["row"]
                
                if apply_discount_delta_to_row(sheet_obj, table, r, delta):
                    updated += 1
            self.last_batch_delta_pp = None
            self._update_session_info_label()
            self._persist_session_state()
            QMessageBox.information(self, "완료", f"총 {updated}개의 중복 모델 항목에 할인율 조정을 적용했습니다.\n(주의: 변경사항은 다른 시트에도 적용되었습니다. 저장 버튼을 눌러 주세요.)")


    def on_apply_discount(self) -> None:
        if not self.loaded:
            return
        table = self._get_selected_table()
        if not table:
            return

        delta_pp = float(self.spin_delta.value())

        try:
            updated, skipped = apply_discount_delta_to_table(self.loaded.ws, table, delta_pp, write_discount_cell=True)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"할인율 적용 중 오류가 발생했습니다.\n\n{e}")
            return

        self.table_deltas_pp[table.index] = delta_pp
        self.last_batch_delta_pp = None
        self._update_session_info_label()
        self._fill_preview(table)
        self._persist_session_state()

        # ?곸슜 ?? 泥???湲곗??쇰줈 蹂寃쎈맂 ?좎씤?⑥쓣 媛꾨떒???덈궡
        ws = self.loaded.ws
        first_ratio = None
        for r in range(table.first_data_row, table.last_data_row + 1):
            val = ws.cell(row=r, column=table.col_discount).value
            rr = parse_discount_ratio(val)
            if rr is not None:
                first_ratio = rr
                break

        extra = f"\n(첫 적용 후 할인율: {first_ratio*100:.2f}%)" if first_ratio is not None else ""
        QMessageBox.information(
            self,
            "완료",
            f"'{table.name}'에 조정값 {delta_pp:.2f}%p를 적용했습니다.\n업데이트: {updated}건\n스킵: {skipped}건{extra}",
        )

    def on_apply_discount_all(self) -> None:
        if not self.loaded:
            return
        if not self.loaded.tables:
            return

        delta_pp = float(self.spin_delta.value())
        if abs(delta_pp) < 1e-9:
            QMessageBox.information(self, "알림", "조정값이 0%p 입니다. 변경할 값으로 입력해 주세요.")
            return

        total_updated = 0
        total_skipped = 0

        try:
            for t in self.loaded.tables:
                updated, skipped = apply_discount_delta_to_table(
                    self.loaded.ws, t, delta_pp, write_discount_cell=True
                )
                total_updated += updated
                total_skipped += skipped
                self.table_deltas_pp[t.index] = delta_pp
        except Exception as e:
            QMessageBox.critical(self, "오류", f"모든 테이블에 적용 중 오류가 발생했습니다.\n\n{e}")
            return

        # ?꾩옱 ?좏깮???뚯씠釉?誘몃━蹂닿린 媛깆떊
        cur = self._get_selected_table()
        if cur:
            self._fill_preview(cur)
        self.last_batch_delta_pp = delta_pp
        self._update_session_info_label()
        self._persist_session_state()

        QMessageBox.information(
            self,
            "완료",
            f"모든 테이블에 조정값 {delta_pp:.2f}%p를 적용했습니다.\n"
            f"총 업데이트: {total_updated}건\n총 스킵: {total_skipped}건",
        )

    def on_compare_prices(self) -> None:
        if not self.loaded:
            return

        ws = self.loaded.ws
        tables = self.loaded.tables
        if not tables:
            QMessageBox.information(self, "알림", "먼저 엑셀에서 테이블을 찾은 뒤 사용해 주세요.")
            return

        # 紐⑤뱺 ?뚯씠釉붿쓽 紐⑤뜽紐??섏쭛
        models: List[str] = []
        for t in tables:
            for r in range(t.first_data_row, t.last_data_row + 1):
                v = ws.cell(row=r, column=t.col_model).value
                if isinstance(v, str) and v.strip():
                    models.append(v.strip())

        if not models:
            QMessageBox.information(self, "알림", "모델명이 있는 행을 찾지 못했습니다.")
            return

        models_set = list(set(models))

        progress = QProgressDialog("다나와 가격 검색 준비 중...", "취소", 0, len(models_set), self)
        progress.setWindowTitle("가격 비교 진행 상황")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        price_map = {}
        try:
            for i, m in enumerate(models_set):
                QApplication.processEvents()
                if progress.wasCanceled():
                    QMessageBox.warning(self, "중단", "가격 비교 조회 작업을 취소했습니다.\n지금까지 찾은 항목까지만 반영합니다.")
                    break
                
                progress.setLabelText(f"다나와 최저가 검색 중... ({i + 1}/{len(models_set)})\n조회 모델: {m}")
                QApplication.processEvents()
                
                price_map[m] = fetch_danawa_lowest_price(m)
                progress.setValue(i + 1)
                
            progress.setValue(len(models_set))
            write_price_comparison(ws, tables, price_map)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "오류", f"가격 비교 중 오류가 발생했습니다.\n\n{e}")
            return

        # 誘몃━蹂닿린 媛깆떊 (?댁? 湲곗〈 誘몃━蹂닿린?먮쭔 異붽?, ?ㅼ젣 ?쒗듃???앸?遺꾩뿉 ?꾨뱶 異붽???
        cur = self._get_selected_table()
        if cur:
            self._fill_preview(cur)
        self.last_batch_delta_pp = None
        self._update_session_info_label()
        self._persist_session_state()

        QMessageBox.information(
            self,
            "완료",
            "다나와 기준 가격 비교 정보를 엑셀 추가 열에 반영했습니다.\n필요하면 결과 값을 다시 확인해 주세요.",
        )

    def on_save(self) -> None:
        if not self.loaded:
            return

        name = self.txt_save_name.text().strip()
        if not name:
            QMessageBox.warning(self, "입력 필요", "저장할 파일명을 입력해 주세요.")
            return

        if not name.lower().endswith(".xlsx"):
            name += ".xlsx"

        # ????꾩튂: ?먮낯 ?뚯씪怨?媛숈? ?대뜑
        out_dir = os.path.dirname(self.loaded.path)
        out_path = os.path.join(out_dir, name)

        try:
            self.loaded.wb.save(out_path)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 중 오류가 발생했습니다.\n\n{e}")
            return

        self._persist_session_state()

        QMessageBox.information(self, "저장 완료", f"저장했습니다.\n\n{out_path}")

    def on_erp_login(self) -> None:
        dlg = ERPLoginDialog(self, self.erp_session)
        if dlg.exec() == QDialog.Accepted:
            self.lbl_erp_status.setText("로그인됨")
            self.lbl_erp_status.setStyleSheet("color: green; font-weight: bold;")
            self.btn_erp_login.setText("ERP 계정 전환")
        else:
            if self.erp_session.is_session_valid():
                self.lbl_erp_status.setText("로그인됨")
                self.lbl_erp_status.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.lbl_erp_status.setText("미로그인 상태")
                self.lbl_erp_status.setStyleSheet("color: red; font-weight: bold;")

        self._sync_inventory_queue_session()
        self._refresh_inventory_queue_status()

    def on_erp_check_row(self) -> None:
        if not self.erp_session.is_session_valid():
            QMessageBox.warning(self, "안내", "먼저 ERP 로그인을 진행해 주세요.")
            return

        cur = self._get_selected_table()
        if not cur:
            QMessageBox.warning(self, "안내", "왼쪽 목록에서 테이블을 먼저 선택해 주세요.")
            return

        selected_ranges = self.tbl_preview.selectedRanges()
        if not selected_ranges:
            QMessageBox.warning(self, "안내", "미리보기 표에서 조회할 행을 선택해 주세요.")
            return

        row = selected_ranges[0].topRow()
        model_item = self.tbl_preview.item(row, 0)
        model_name = model_item.text().strip().upper() if model_item else ""
        if not model_name:
            QMessageBox.warning(self, "안내", "선택한 행에 모델명이 없습니다.")
            return

        status_dlg = InventorySearchStatusDialog(self, model_name)
        status_dlg.show_centered_on_parent()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            status_dlg.set_status("ERP 모델 목록 검색 중...")
            models = self.erp_client.query_full_model(model_name)
            if models:
                status_dlg.set_status(f"{len(models)}개 모델 조회 중... (재고·생산계획)")
            lookup = self.erp_client.select_best_inventory_model(model_name, models) if models else None
        finally:
            QApplication.restoreOverrideCursor()
            status_dlg.close()

        if not models:
            detail = self.erp_client.last_error.strip()
            if detail:
                QMessageBox.warning(
                    self,
                    "ERP 모델 조회 실패",
                    f"'{model_name}' 모델 조회에 실패했습니다.\n\n원인: {detail}\n\n세션 만료나 연동 오류일 수 있으니 ERP 로그인을 다시 시도해 주세요.",
                )
            else:
                QMessageBox.information(self, "검색 실패", f"'{model_name}' 모델을 ERP에서 찾을 수 없습니다.")
            return

        if not lookup:
            detail = self.erp_client.last_error.strip()
            QMessageBox.information(
                self,
                "조회 결과 없음",
                detail or f"'{model_name}' 기준으로 조회 가능한 모델을 찾지 못했습니다.",
            )
            return

        dlg = InventoryMultipleResultDialog(self, self._format_inventory_lookup_text(lookup))
        dlg.setWindowTitle("ERP 재고/생산계획 조회 결과")
        dlg.exec()
    def on_manual_inventory_search(self) -> None:
        model_name = self.txt_manual_model.text().strip().upper()
        if not model_name:
            QMessageBox.warning(self, "안내", "모델명을 입력해 주세요.")
            return

        if not self.erp_session.is_session_valid():
            QMessageBox.warning(self, "안내", "먼저 ERP 로그인을 진행해 주세요.")
            return

        status_dlg = InventorySearchStatusDialog(self, model_name)
        status_dlg.show_centered_on_parent()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            status_dlg.set_status("ERP 모델 목록 검색 중...")
            models = self.erp_client.query_full_model(model_name)
            if models:
                status_dlg.set_status(f"{len(models)}개 모델 조회 중... (재고·생산계획)")
            lookup = self.erp_client.select_best_inventory_model(model_name, models) if models else None
        finally:
            QApplication.restoreOverrideCursor()
            status_dlg.close()

        if not models:
            detail = self.erp_client.last_error.strip()
            if detail:
                QMessageBox.warning(
                    self,
                    "ERP 모델 조회 실패",
                    f"'{model_name}' 모델 조회에 실패했습니다.\n\n원인: {detail}\n\n세션 만료나 연동 오류일 수 있으니 ERP 로그인을 다시 시도해 주세요.",
                )
            else:
                QMessageBox.information(self, "검색 실패", f"'{model_name}' 모델을 ERP에서 찾을 수 없습니다.")
            return

        if not lookup:
            detail = self.erp_client.last_error.strip()
            QMessageBox.information(
                self,
                "조회 결과 없음",
                detail or f"'{model_name}' 기준으로 조회 가능한 모델을 찾지 못했습니다.",
            )
            return

        dlg = InventoryMultipleResultDialog(self, self._format_inventory_lookup_text(lookup))
        dlg.setWindowTitle("개별 모델 재고/생산계획 조회 결과")
        dlg.exec()

    def _check_erp_keepalive(self) -> None:
        """60초마다 호출: 마지막 접속 후 15분이 지나면 세션 유지 요청을 보냅니다."""
        import time

        if not self.erp_session.is_session_valid():
            self.lbl_erp_keepalive.setText("")
            return

        last = self.erp_session.last_activity_time
        now = time.time()
        elapsed = (now - last) if last > 0 else self.ERP_KEEPALIVE_INTERVAL_SEC + 1
        remaining = self.ERP_KEEPALIVE_INTERVAL_SEC - elapsed

        if remaining <= 0:
            # 15분 경과 → 세션 유지 요청
            self.lbl_erp_keepalive.setText("🔄 세션 유지 중...")
            QApplication.processEvents()
            ok = self.erp_session.keep_alive()
            if ok:
                next_min = self.ERP_KEEPALIVE_INTERVAL_SEC // 60
                self.lbl_erp_keepalive.setText(f"✅ 유지됨 (다음: {next_min}분 후)")
            else:
                self.lbl_erp_keepalive.setText("⚠️ 세션 유지 실패")
                # 세션 만료 감지 시 자동 재시작 처리
                self._handle_session_expiry()
        else:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            self.lbl_erp_keepalive.setText(f"(유지: {mins}분 {secs}초 후)")

    def _restart_application(self) -> None:
        """현재 프로세스를 종료하고 새 프로세스로 재시작합니다."""
        try:
            self._persist_session_metadata_only()
            self.inventory_queue.stop()
        except Exception:
            pass

        python = sys.executable
        prev_count = 0
        for a in sys.argv:
            if a.startswith("--restart-count="):
                try:
                    prev_count = int(a.split("=", 1)[1])
                except ValueError:
                    pass
        args = (
            [a for a in sys.argv[:] if a != "--auto-login" and not a.startswith("--restart-count=")]
            + ["--auto-login", f"--restart-count={prev_count + 1}"]
        )

        # 스크립트 실행(python main.py)과 빌드된 EXE 실행 환경을 모두 지원
        if python.lower() == args[0].lower() or (args[0] == "" and len(args) == 1):
            # 빌드된 EXE 환경: sys.executable과 argv[0]이 같음
            os.execl(python, *args)
        else:
            # 스크립트 실행 환경: 첫 번째 인자로 interpreter를 명시
            os.execl(python, python, *args)

    def _handle_session_expiry(self) -> None:
        """세션 만료 알림을 표시하고 잠시 후 자동 재시작합니다."""
        # 중복 호출 방지를 위해 타이머 정지
        if hasattr(self, "erp_keepalive_timer"):
            self.erp_keepalive_timer.stop()
            
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("ERP 세션 만료")
        msg.setText("ERP 세션이 만료되거나 유지가 불가능합니다.\n\n안정적인 연동을 위해 프로그램을 자동으로 재시작합니다.\n잠시만 기다려 주세요...")
        msg.setStandardButtons(QMessageBox.NoButton) # 사용자가 확인을 누를 필요 없도록 버튼 제거
        msg.show()
        
        # UI에 메시지가 보일 시간을 주기 위해 2.5초 후 재시작 실행
        QTimer.singleShot(2500, self._restart_application)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._persist_session_metadata_only()
        self.inventory_status_timer.stop()
        self.erp_keepalive_timer.stop()
        self.inventory_queue.stop()
        if self._last_temp_path and os.path.exists(self._last_temp_path):
            try:
                os.remove(self._last_temp_path)
            except OSError:
                pass
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    
    # Splash Screen
    splash_path = resource_path("splash.png")
    if os.path.exists(splash_path):
        splash_pix = QPixmap(splash_path)
        splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()
    else:
        splash = None
        
    w = MainWindow()
    w.show()
    
    if splash:
        splash.finish(w)
        
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())



