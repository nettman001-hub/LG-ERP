import os
import sys
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap, QIcon, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QApplication,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QDialog,
    QTextEdit,
)


def resource_path(relative_path: str) -> str:
    """PyInstaller 실행 환경 및 개발 환경 모두 지원하는 경로 반환"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class ClickableLabel(QLabel):
    """클릭 가능한 라벨 (공지사항 및 오늘 할 일 항목용)"""
    clicked = Signal()

    def __init__(self, text: str = "", parent: QWidget = None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class BestSecretaryDialog(QDialog):
    """BEST 비서 AI 업무 브리핑 팝업"""
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("BEST AI 영업 비서 브리핑")
        self.resize(480, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("🤖 BEST 스마트 AI 비서")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a1c24;")
        layout.addWidget(header)

        briefing = QTextEdit()
        briefing.setReadOnly(True)
        briefing.setStyleSheet("""
            QTextEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.6;
                color: #334155;
            }
        """)
        briefing_text = (
            "안녕하세요, <b>정확현님!</b> 오늘 영업 현황 브리핑입니다. ☀️\n\n"
            "📊 <b>오늘의 주요 지표 요약</b>\n"
            "• 신규 접수 주문: 총 12건 (수도권 8건, 지방 4건)\n"
            "• 당일 배송 예정: 5건 (설치 기사 배정 완료)\n"
            "• 약속일 변경 요청: 2건 (고객 협의 필요)\n\n"
            "⚠️ <b>긴급 재고 및 가격 알림</b>\n"
            "• <i>OLED65C4QNA</i> 평택 중앙물류 재고 15대 미만으로 안전재고 도달\n"
            "• 4월 에어컨 기획전 공급가 조정 검토 요망\n\n"
            "💡 <b>추천 작업</b>\n"
            "상단 <b>[✨ AI서비스 (엑셀 가격표)]</b> 버튼을 눌러 최신 할인율을 검토하고 다나와 최저가와 비교해 보세요!"
        )
        briefing.setHtml(briefing_text)
        layout.addWidget(briefing)

        btn_close = QPushButton("확인 및 닫기")
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #e6004c;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c40040;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class LGErpMainView(QWidget):
    """
    LG B2B ERP (NEW BEST) 메인 화면 인터랙티브 데모 뷰.
    메뉴, 공지사항, 오늘 할 일 등을 클릭하면 실제 ERP 서브 페이지로 전환됩니다.
    """
    ai_service_clicked = Signal()
    search_model_requested = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("LGErpMainView")
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 0. Edge 브라우저 스타일 URL 주소표시줄
        url_bar = self._create_browser_url_bar()
        main_layout.addWidget(url_bar)

        # 1. 최상단 탑바 (Top Bar)
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        # 2. GNB 네비게이션 메뉴바
        gnb_bar = self._create_gnb_bar()
        main_layout.addWidget(gnb_bar)

        # 3. 본문 스택 위젯 (각 페이지별 동적 전환)
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentStack")

        # Index 0: 메인 대시보드 홈
        self.dashboard_home = self._create_dashboard_home()
        self.content_stack.addWidget(self.dashboard_home)

        # Index 1: 마스터 품목 기준정보
        self.page_master = self._create_master_page()
        self.content_stack.addWidget(self.page_master)

        # Index 2: 납품/인사 배정 관리
        self.page_delivery = self._create_delivery_page()
        self.content_stack.addWidget(self.page_delivery)

        # Index 3: 구매/환입 발주 관리
        self.page_purchase = self._create_purchase_page()
        self.content_stack.addWidget(self.page_purchase)

        # Index 4: 창고별 재고 및 이관
        self.page_inventory = self._create_inventory_page()
        self.content_stack.addWidget(self.page_inventory)

        # Index 5: 판매 주문 및 배송 추적
        self.page_sales = self._create_sales_page()
        self.content_stack.addWidget(self.page_sales)

        # Index 6: 결산 및 LGE 본사 거래
        self.page_settlement = self._create_settlement_page()
        self.content_stack.addWidget(self.page_settlement)

        # Index 7: 오늘 꼭 해야 할 일 상세
        self.page_todo = self._create_todo_detail_page()
        self.content_stack.addWidget(self.page_todo)

        # Index 8: 공지사항 상세 보기
        self.page_notice = self._create_notice_detail_page()
        self.content_stack.addWidget(self.page_notice)

        main_layout.addWidget(self.content_stack, 1)
        self.setStyleSheet(self._get_stylesheet())

        # 기본 페이지: 대시보드 홈
        self.go_dashboard_home()

    def _create_browser_url_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("BrowserUrlBar")
        bar.setFixedHeight(34)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        lbl_edge = QLabel("🌐")
        lbl_edge.setStyleSheet("font-size: 13px; color: #0284c7;")
        layout.addWidget(lbl_edge)

        lbl_lock = QLabel("🔒")
        lbl_lock.setStyleSheet("font-size: 11px; color: #10b981;")
        layout.addWidget(lbl_lock)

        self.lbl_url = QLabel("https://newbest.lge.com/b2b/NEWBEST/index.jsp")
        self.lbl_url.setObjectName("BrowserUrlLabel")
        self.lbl_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_url, 1)

        btn_refresh = QPushButton("⟳")
        btn_refresh.setToolTip("새로고침 (홈으로 이동)")
        btn_refresh.setCursor(QCursor(Qt.PointingHandCursor))
        btn_refresh.setStyleSheet("background: transparent; border: none; font-size: 14px; color: #64748b;")
        btn_refresh.clicked.connect(self.go_dashboard_home)
        layout.addWidget(btn_refresh)

        return bar

    def _create_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(44)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # 좌측 BEST 로고 (클릭 시 홈으로)
        btn_logo = QPushButton("BEST")
        btn_logo.setObjectName("LogoBtn")
        btn_logo.setCursor(QCursor(Qt.PointingHandCursor))
        btn_logo.clicked.connect(self.go_dashboard_home)
        layout.addWidget(btn_logo)

        # 모델 통합 검색 입력창
        search_box = QFrame()
        search_box.setObjectName("SearchBox")
        search_layout = QHBoxLayout(search_box)
        search_layout.setContentsMargins(10, 0, 8, 0)
        search_layout.setSpacing(6)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("SearchInput")
        self.txt_search.setPlaceholderText("모델통합검색")
        self.txt_search.returnPressed.connect(self._on_search_enter)
        search_layout.addWidget(self.txt_search)

        btn_search_icon = QPushButton("🔍")
        btn_search_icon.setObjectName("SearchBtn")
        btn_search_icon.setCursor(QCursor(Qt.PointingHandCursor))
        btn_search_icon.clicked.connect(self._on_search_enter)
        search_layout.addWidget(btn_search_icon)

        layout.addWidget(search_box)
        layout.addStretch()

        # 우측 유저 프로필 및 도구들
        lbl_user = QLabel("정확현님")
        lbl_user.setObjectName("UserNameLabel")
        layout.addWidget(lbl_user)

        lbl_bell = QLabel("🔔")
        lbl_bell.setObjectName("TopIcon")
        layout.addWidget(lbl_bell)

        btn_secretary = QPushButton("🤖 BEST 비서")
        btn_secretary.setObjectName("BestSecretaryBtn")
        btn_secretary.setCursor(QCursor(Qt.PointingHandCursor))
        btn_secretary.clicked.connect(self._open_best_secretary)
        layout.addWidget(btn_secretary)

        btn_quick = QPushButton("★ 퀵메뉴")
        btn_quick.setObjectName("TopToolBtn")
        btn_quick.setCursor(QCursor(Qt.PointingHandCursor))
        btn_quick.clicked.connect(lambda: self.switch_page(1, "https://newbest.lge.com/b2b/NEWBEST/master/itemList.do"))
        layout.addWidget(btn_quick)

        btn_link = QPushButton("🔗 링크")
        btn_link.setObjectName("TopToolBtn")
        btn_link.setCursor(QCursor(Qt.PointingHandCursor))
        btn_link.clicked.connect(lambda: self.switch_page(4, "https://newbest.lge.com/b2b/NEWBEST/inventory/stockList.do"))
        layout.addWidget(btn_link)

        btn_collapse = QPushButton("☰ 메뉴접기")
        btn_collapse.setObjectName("TopToolBtn")
        btn_collapse.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(btn_collapse)

        btn_org = QPushButton("👥 조직전환")
        btn_org.setObjectName("TopToolBtn")
        btn_org.setCursor(QCursor(Qt.PointingHandCursor))
        btn_org.clicked.connect(lambda: self.switch_page(6, "https://newbest.lge.com/b2b/NEWBEST/settlement/monthlyClose.do"))
        layout.addWidget(btn_org)

        lbl_mail = QLabel("✉️")
        lbl_mail.setObjectName("TopIcon")
        layout.addWidget(lbl_mail)

        lbl_logout = QLabel("🚪")
        lbl_logout.setObjectName("TopIcon")
        layout.addWidget(lbl_logout)

        return bar

    def _create_gnb_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("GnbBar")
        bar.setFixedHeight(38)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(40, 0, 40, 0)
        layout.setSpacing(4)

        # 메뉴 정의: (이름, 이동할 페이지 인덱스, URL)
        menu_items = [
            ("마스터", 1, "https://newbest.lge.com/b2b/NEWBEST/master/itemList.do"),
            ("납품/인사", 2, "https://newbest.lge.com/b2b/NEWBEST/delivery/assignList.do"),
            ("구매/환입", 3, "https://newbest.lge.com/b2b/NEWBEST/purchase/orderList.do"),
            ("재고/이관", 4, "https://newbest.lge.com/b2b/NEWBEST/inventory/stockList.do"),
            ("판매/배송", 5, "https://newbest.lge.com/b2b/NEWBEST/sales/orderTracking.do"),
            ("결산/LGE거래", 6, "https://newbest.lge.com/b2b/NEWBEST/settlement/monthlyClose.do"),
        ]

        for name, page_idx, url in menu_items:
            btn = QPushButton(name)
            btn.setObjectName("GnbMenuBtn")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _, idx=page_idx, u=url: self.switch_page(idx, u))
            layout.addWidget(btn, 1)

        # ★ 핵심 요구사항: "AI서비스" 버튼 (가격표 조정기 화면 호출)
        self.btn_ai_service = QPushButton("✨ AI서비스 (엑셀 가격표)")
        self.btn_ai_service.setObjectName("AiServiceBtn")
        self.btn_ai_service.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_ai_service.setToolTip("클릭하여 엑셀 가격표 할인율 조정기로 진입합니다")
        self.btn_ai_service.clicked.connect(self.ai_service_clicked.emit)
        layout.addWidget(self.btn_ai_service, 1)

        return bar

    # -------------------------------------------------------------
    # 화면 전환 헬퍼
    # -------------------------------------------------------------
    def switch_page(self, index: int, url: str):
        self.content_stack.setCurrentIndex(index)
        self.lbl_url.setText(url)

    def go_dashboard_home(self):
        self.switch_page(0, "https://newbest.lge.com/b2b/NEWBEST/index.jsp")

    def _open_best_secretary(self):
        dlg = BestSecretaryDialog(self)
        dlg.exec()

    # -------------------------------------------------------------
    # Page 0: 메인 대시보드 홈
    # -------------------------------------------------------------
    def _create_dashboard_home(self) -> QWidget:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(10)

        # 3-1. 히어로 배너 영역
        banner_widget = self._create_hero_banner()
        content_layout.addWidget(banner_widget)

        # 3-2. 오늘 꼭 해야 할 일 섹션
        todo_widget = self._create_todo_section()
        content_layout.addWidget(todo_widget)

        # 3-3. 하단 2분할 공지사항 섹션
        notices_widget = self._create_notices_section()
        content_layout.addWidget(notices_widget)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        return scroll_area

    def _create_hero_banner(self) -> QWidget:
        container = QFrame()
        container.setObjectName("BannerContainer")
        container.setFixedHeight(215)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        banner_img_path = resource_path("banner_hero.png")
        lbl_banner = QLabel()
        lbl_banner.setObjectName("BannerImageLabel")
        lbl_banner.setAlignment(Qt.AlignCenter)

        if os.path.exists(banner_img_path):
            pix = QPixmap(banner_img_path)
            lbl_banner.setPixmap(pix)
            lbl_banner.setScaledContents(True)
        else:
            lbl_banner.setText("NEW BEST - Smart life Solution Company LG")
            lbl_banner.setStyleSheet("font-size: 20px; font-weight: bold; color: #d81a50;")

        layout.addWidget(lbl_banner)
        return container

    def _create_todo_section(self) -> QWidget:
        card = QFrame()
        card.setObjectName("TodoCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 타이틀
        title_layout = QHBoxLayout()
        icon_lbl = QLabel("💼")
        title_lbl = QLabel("영업 오늘 꼭 해야 할 일")
        title_lbl.setObjectName("TodoTitle")
        title_layout.addWidget(icon_lbl)
        title_layout.addWidget(title_lbl)

        btn_all_todos = QPushButton("전체 처리목록 이동 >")
        btn_all_todos.setObjectName("SubActionBtn")
        btn_all_todos.setCursor(QCursor(Qt.PointingHandCursor))
        btn_all_todos.clicked.connect(lambda: self.switch_page(7, "https://newbest.lge.com/b2b/NEWBEST/task/todayTodoList.do"))
        title_layout.addStretch()
        title_layout.addWidget(btn_all_todos)
        layout.addLayout(title_layout)

        items_layout = QHBoxLayout()
        items_layout.setSpacing(40)

        # 1열
        col1_layout = QVBoxLayout()
        col1_layout.setSpacing(6)
        item1 = ClickableLabel("✔  전일대비 약속일 변경건 (2건)")
        item1.setObjectName("TodoClickItem")
        item1.clicked.connect(lambda: self._show_todo_detail("약속일 변경건"))
        item2 = ClickableLabel("✔  자동 적자 예상건 (1건)")
        item2.setObjectName("TodoClickItem")
        item2.clicked.connect(lambda: self._show_todo_detail("자동 적자 예상건"))
        col1_layout.addWidget(item1)
        col1_layout.addWidget(item2)
        items_layout.addLayout(col1_layout)

        # 2열
        col2_layout = QVBoxLayout()
        col2_layout.setSpacing(6)
        item3 = ClickableLabel("✔  당일 배송 예정건 (5건)")
        item3.setObjectName("TodoClickItem")
        item3.clicked.connect(lambda: self._show_todo_detail("당일 배송 예정건"))
        col2_layout.addWidget(item3)
        col2_layout.addStretch()
        items_layout.addLayout(col2_layout)

        items_layout.addStretch()
        layout.addLayout(items_layout)

        return card

    def _create_notices_section(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        sales_card = self._create_sales_notices()
        layout.addWidget(sales_card, 1)

        it_card = self._create_it_notices()
        layout.addWidget(it_card, 1)

        return container

    def _create_sales_notices(self) -> QWidget:
        card = QFrame()
        card.setObjectName("NoticeCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(12)

        lbl_title = QLabel("영업공지사항")
        lbl_title.setObjectName("NoticeTitle")
        tab_layout.addWidget(lbl_title)

        tab_all = QPushButton("전체")
        tab_all.setObjectName("NoticeTabActive")
        tab_layout.addWidget(tab_all)

        tab_gen = QPushButton("일반공지")
        tab_gen.setObjectName("NoticeTab")
        tab_layout.addWidget(tab_gen)

        tab_inst = QPushButton("설치자")
        tab_inst.setObjectName("NoticeTab")
        tab_layout.addWidget(tab_inst)

        tab_layout.addStretch()

        btn_more = QPushButton("+ 더보기")
        btn_more.setObjectName("NoticeMoreBtn")
        btn_more.setCursor(QCursor(Qt.PointingHandCursor))
        btn_more.clicked.connect(lambda: self._show_notice_detail("전국 물류 주소록 (26년 8/18일 기준)", "2026-08-24", "영업공지사항"))
        tab_layout.addWidget(btn_more)
        layout.addLayout(tab_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(line)

        notices = [
            ("일반", "전국 물류 주소록 (26년 8/18일 기준)", "2026-08-24", True),
            ("일반", "[추가안내] 고객 협의 없는 구제번 제품 시공 절대금지 - 무분수가 일부교체현장...", "2025-12-24", False),
            ("일반", "[안내] - 고객협의없는 구세번제품시공 절대금지_고객 협의 증빙서류 수취 및 보관", "2025-11-20", False),
            ("일반", "[추가안내] 고객 협의 없는 구제번 제품 시공 절대금지 - 현장에서 제번 확인 필수", "2025-11-03", False),
        ]

        for category, title, date, is_highlight in notices:
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl_cat = QLabel(category)
            lbl_cat.setObjectName("NoticeCategory")
            lbl_cat.setFixedWidth(32)
            row.addWidget(lbl_cat)

            lbl_title = ClickableLabel(title)
            lbl_title.setObjectName("NoticeHighlightTitle" if is_highlight else "NoticeItemTitle")
            lbl_title.clicked.connect(lambda t=title, d=date: self._show_notice_detail(t, d, "영업공지사항"))
            row.addWidget(lbl_title, 1)

            lbl_date = QLabel(date)
            lbl_date.setObjectName("NoticeDateHighlight" if is_highlight else "NoticeDate")
            row.addWidget(lbl_date)

            layout.addLayout(row)

        layout.addStretch()
        return card

    def _create_it_notices(self) -> QWidget:
        card = QFrame()
        card.setObjectName("NoticeCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(12)

        lbl_title = QLabel("전산공지사항")
        lbl_title.setObjectName("NoticeTitle")
        tab_layout.addWidget(lbl_title)

        tab_layout.addStretch()

        btn_more = QPushButton("+ 더보기")
        btn_more.setObjectName("NoticeMoreBtn")
        btn_more.setCursor(QCursor(Qt.PointingHandCursor))
        btn_more.clicked.connect(lambda: self._show_notice_detail("[New BEST] 출하보류 해지요청 메일발송 기능 반영", "2026-08-25", "전산공지사항"))
        tab_layout.addWidget(btn_more)
        layout.addLayout(tab_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(line)

        notices = [
            ("[New BEST] 출하보류 해지요청 메일발송 기능 반영 (2026-08-25)", "2026-08-25", True),
            ("[New BEST] LGE 주문 조회 화면 변경사항 안내(2026-08-19)", "2026-08-19", False),
            ("[New BEST] 알림 기능 파일럿 운영 - 신고확인서 알림", "2026-08-05", False),
            ("[안내] New BEST 세션타임아웃 시간 변경 건", "2026-08-03", False),
        ]

        for title, date, is_highlight in notices:
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl_title = ClickableLabel(title)
            lbl_title.setObjectName("NoticeHighlightTitle" if is_highlight else "NoticeItemTitle")
            lbl_title.clicked.connect(lambda t=title, d=date: self._show_notice_detail(t, d, "전산공지사항"))
            row.addWidget(lbl_title, 1)

            lbl_date = QLabel(date)
            lbl_date.setObjectName("NoticeDateHighlight" if is_highlight else "NoticeDate")
            row.addWidget(lbl_date)

            layout.addLayout(row)

        layout.addStretch()
        return card

    # -------------------------------------------------------------
    # Page 1: 마스터 품목 기준정보 페이지
    # -------------------------------------------------------------
    def _create_master_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # 상단 네비게이션 헤더
        header = self._create_page_header("홈 > 마스터 > 품목기준정보 관리", "📦 품목 기준정보 마스터")
        layout.addLayout(header)

        # 필터 검색 바
        filter_frame = QFrame()
        filter_frame.setObjectName("FilterFrame")
        f_layout = QHBoxLayout(filter_frame)
        f_layout.addWidget(QLabel("품목코드:"))
        txt_code = QLineEdit()
        txt_code.setPlaceholderText("예: OLED65, F21")
        f_layout.addWidget(txt_code)

        f_layout.addWidget(QLabel("제품 카테고리:"))
        txt_cat = QLineEdit()
        txt_cat.setPlaceholderText("전체 카테고리")
        f_layout.addWidget(txt_cat)

        btn_search = QPushButton("🔍 조회")
        btn_search.setObjectName("PrimaryActionBtn")
        f_layout.addWidget(btn_search)
        f_layout.addStretch()
        layout.addWidget(filter_frame)

        # 품목 테이블
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["품목코드", "품목명", "규격/사양", "카테고리", "기본공급가", "판매상태"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)

        items = [
            ("OLED65C4QNA", "LG 올레드 evo 65형", "4K 144Hz 알파9 AI 프로세서", "TV/AV", "₩2,850,000", "판매중"),
            ("F21WDNP", "LG 트롬 드럼세탁기 21kg", "인공지능 DD모터 / 화이트", "세탁기", "₩1,280,000", "판매중"),
            ("M874MWW451", "LG 디오스 오브제컬렉션 무드업", "4도어 874L 노크온", "냉장고", "₩3,420,000", "판매중"),
            ("FQ18EN9B02", "LG 휘센 오브제 타워2 에어컨", "18평형 2in1 듀얼인버터", "에어컨", "₩2,150,000", "판매중"),
            ("AU9982GD", "LG 코드제로 오브제컬렉션 A9S", "올인원타워 흡입+물걸레", "청소기", "₩890,000", "판매중"),
            ("S5MBP", "LG 스타일러 오브제컬렉션", "5벌+바지1벌 미러블랙", "스타일러", "₩1,450,000", "판매중"),
        ]

        table.setRowCount(len(items))
        for r, row in enumerate(items):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if c in (0, 3, 5) else Qt.AlignVCenter)
                table.setItem(r, c, item)

        layout.addWidget(table)
        return widget

    # -------------------------------------------------------------
    # Page 2: 납품/인사 배정 관리 페이지
    # -------------------------------------------------------------
    def _create_delivery_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = self._create_page_header("홈 > 납품/인사 > 납품 및 기사 배정 현황", "🚚 납품 및 설치기사 배정 현황")
        layout.addLayout(header)

        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["납품번호", "고객명", "수령지 주소", "주문품목", "배정기사", "설치예정일", "상태"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        deliveries = [
            ("DL-20260401-01", "김*수 고객님", "서울시 강남구 역삼로 123", "OLED65C4QNA", "이철수 기사", "2026-04-01 14:00", "이동중"),
            ("DL-20260401-02", "박*영 고객님", "경기도 성남시 분당구 정자일로 45", "F21WDNP 외 1건", "정민호 기사", "2026-04-01 16:30", "배정완료"),
            ("DL-20260401-03", "최*준 고객님", "인천시 연수구 송도과학로 88", "M874MWW451", "강현우 기사", "2026-04-02 10:00", "배정완료"),
            ("DL-20260401-04", "이*진 고객님", "서울시 송파구 올림픽로 300", "FQ18EN9B02", "김태성 기사", "2026-04-02 13:00", "대기중"),
        ]

        table.setRowCount(len(deliveries))
        for r, row in enumerate(deliveries):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                table.setItem(r, c, item)

        layout.addWidget(table)
        return widget

    # -------------------------------------------------------------
    # Page 3: 구매/환입 발주 관리 페이지
    # -------------------------------------------------------------
    def _create_purchase_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = self._create_page_header("홈 > 구매/환입 > 구매 발주 및 환입 관리", "📝 구매 발주 및 환입 처리")
        layout.addLayout(header)

        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["발주일자", "발주번호", "공급처", "품목", "수량", "입고창고", "승인상태"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        orders = [
            ("2026-03-31", "PO-2603-0891", "LG전자 본사 물류", "OLED65C4QNA", "30대", "평택중앙물류", "입고완료"),
            ("2026-03-31", "PO-2603-0892", "LG전자 창원1공장", "F21WDNP", "20대", "곤지암물류", "배송중"),
            ("2026-03-30", "PO-2603-0885", "LG전자 본사 물류", "M874MWW451", "15대", "평택중앙물류", "승인완료"),
            ("2026-03-28", "RT-2603-0012", "다온솔루션 물류", "AU9982GD (환입)", "2대", "불량검수센터", "환입완료"),
        ]

        table.setRowCount(len(orders))
        for r, row in enumerate(orders):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                table.setItem(r, c, item)

        layout.addWidget(table)
        return widget

    # -------------------------------------------------------------
    # Page 4: 창고별 재고 및 이관 페이지
    # -------------------------------------------------------------
    def _create_inventory_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = self._create_page_header("홈 > 재고/이관 > 창고별 실시간 재고/이관", "🏢 창고별 실시간 가용 재고 및 이관")
        layout.addLayout(header)

        # 요약 카드 3개
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)
        wh_data = [
            ("평택 중앙물류센터", "1,420 대", "#0284c7"),
            ("곤지암 허브물류", "890 대", "#10b981"),
            ("창원 공장직송창고", "2,150 대", "#8b5cf6"),
        ]
        for name, qty, color in wh_data:
            c = QFrame()
            c.setStyleSheet(f"background: #ffffff; border: 1px solid #cbd5e1; border-left: 4px solid {color}; border-radius: 4px; padding: 8px;")
            cl = QVBoxLayout(c)
            cl.addWidget(QLabel(name))
            ql = QLabel(qty)
            ql.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
            cl.addWidget(ql)
            cards_layout.addWidget(c)
        layout.addLayout(cards_layout)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["품목코드", "품목명", "평택중앙", "곤지암", "창원직송", "총 가용재고"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        stocks = [
            ("OLED65C4QNA", "LG 올레드 evo 65형", "14대", "8대", "45대", "67대"),
            ("F21WDNP", "LG 트롬 드럼세탁기 21kg", "28대", "15대", "60대", "103대"),
            ("M874MWW451", "LG 디오스 오브제컬렉션", "9대", "5대", "30대", "44대"),
            ("FQ18EN9B02", "LG 휘센 타워2 에어컨", "35대", "22대", "80대", "137대"),
            ("AU9982GD", "LG 코드제로 A9S 청소기", "50대", "30대", "110대", "190대"),
        ]

        table.setRowCount(len(stocks))
        for r, row in enumerate(stocks):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                table.setItem(r, c, item)

        layout.addWidget(table)
        return widget

    # -------------------------------------------------------------
    # Page 5: 판매 주문 및 배송 추적 페이지
    # -------------------------------------------------------------
    def _create_sales_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = self._create_page_header("홈 > 판매/배송 > 판매 주문 및 배송 추적", "🛍️ 실시간 판매 주문 및 배송 현황")
        layout.addLayout(header)

        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["주문번호", "주문일시", "고객명", "주문금액", "배송구분", "송장번호", "진행상태"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        sales = [
            ("ORD-260401-001", "2026-04-01 09:15", "홍*동", "₩2,850,000", "직접설치배송", "LG-LOGIS-9912", "배송출발"),
            ("ORD-260401-002", "2026-04-01 09:42", "이*영", "₩1,280,000", "전문설치", "LG-LOGIS-9913", "기사배정"),
            ("ORD-260401-003", "2026-04-01 10:05", "송*재", "₩3,420,000", "전문설치", "LG-LOGIS-9914", "물류상차"),
            ("ORD-260401-004", "2026-04-01 10:30", "윤*희", "₩890,000", "택배배송", "CJ-대한통운-4412", "접수완료"),
        ]

        table.setRowCount(len(sales))
        for r, row in enumerate(sales):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                table.setItem(r, c, item)

        layout.addWidget(table)
        return widget

    # -------------------------------------------------------------
    # Page 6: 결산 및 LGE 본사 거래 내역 페이지
    # -------------------------------------------------------------
    def _create_settlement_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = self._create_page_header("홈 > 결산/LGE거래 > 월별 정산 및 채권 관리", "💰 월별 정산 및 LGE 본사 거래 내역")
        layout.addLayout(header)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["정산월", "거래구분", "총공급가액", "부가세", "본사장려금(인센티브)", "정산승인상태"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        settlements = [
            ("2026년 03월", "B2C 가이드 가전정산", "₩184,500,000", "₩18,450,000", "₩12,300,000", "정산마감(완료)"),
            ("2026년 02월", "B2C 가이드 가전정산", "₩162,100,000", "₩16,210,000", "₩10,800,000", "정산마감(완료)"),
            ("2026년 01월", "B2C 가이드 가전정산", "₩195,400,000", "₩19,540,000", "₩14,200,000", "정산마감(완료)"),
        ]

        table.setRowCount(len(settlements))
        for r, row in enumerate(settlements):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                table.setItem(r, c, item)

        layout.addWidget(table)
        return widget

    # -------------------------------------------------------------
    # Page 7: 오늘 꼭 해야 할 일 상세 목록 페이지
    # -------------------------------------------------------------
    def _create_todo_detail_page(self) -> QWidget:
        widget = QWidget()
        self.todo_page_layout = QVBoxLayout(widget)
        self.todo_page_layout.setContentsMargins(16, 12, 16, 16)
        self.todo_page_layout.setSpacing(12)

        header = self._create_page_header("홈 > 영업지원 > 오늘 꼭 해야 할 일", "💼 영업 오늘 꼭 해야 할 일 세부 처리")
        self.todo_page_layout.addLayout(header)

        self.lbl_todo_category = QLabel("전체 업무 내역")
        self.lbl_todo_category.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        self.todo_page_layout.addWidget(self.lbl_todo_category)

        self.todo_table = QTableWidget()
        self.todo_table.setColumnCount(5)
        self.todo_table.setHorizontalHeaderLabels(["구분", "관련 고객/주문", "대상 모델", "세부 조치사항", "처리상태"])
        self.todo_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.todo_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self._populate_todo_table("전체")
        self.todo_page_layout.addWidget(self.todo_table)
        return widget

    def _show_todo_detail(self, category: str):
        self.lbl_todo_category.setText(f"선택 분류: {category}")
        self._populate_todo_table(category)
        self.switch_page(7, f"https://newbest.lge.com/b2b/NEWBEST/task/todayTodoList.do?cat={category}")

    def _populate_todo_table(self, filter_cat: str):
        all_todos = [
            ("약속일 변경건", "ORD-260328-04 김*수", "OLED65C4QNA", "고객 요청으로 4/3일에서 4/5일로 배송일정 연기 협의 완료", "협의완료"),
            ("약속일 변경건", "ORD-260329-11 박*영", "M874MWW451", "인테리어 공사 지연으로 설치일 미정 통보 -> 확인 전화 필요", "확인필요"),
            ("당일 배송 예정건", "ORD-260401-01 이*철", "F21WDNP", "오전 11시 기사 상차 완료, 오후 2시 설치 예정", "배송중"),
            ("당일 배송 예정건", "ORD-260401-02 최*준", "FQ18EN9B02", "오후 4시 서울 송파구 직배송 예정", "상차대기"),
            ("당일 배송 예정건", "ORD-260401-05 윤*희", "AU9982GD", "오후 5시 30분 안산 단원구 배송 예정", "배정완료"),
            ("자동 적자 예상건", "기획전 특가 모델", "S5MBP (스타일러)", "다나와 최저가 하락으로 공급가 마진 역전 위험 -> 할인율 재조정 필요", "조정요망"),
        ]

        filtered = all_todos if filter_cat == "전체" else [t for t in all_todos if filter_cat in t[0]]
        self.todo_table.setRowCount(len(filtered))
        for r, row in enumerate(filtered):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                self.todo_table.setItem(r, c, item)

    # -------------------------------------------------------------
    # Page 8: 공지사항 상세 보기 페이지
    # -------------------------------------------------------------
    def _create_notice_detail_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = self._create_page_header("홈 > 공지사항 > 공지사항 상세 조회", "📢 공지사항 상세")
        layout.addLayout(header)

        # 공지 카드
        card = QFrame()
        card.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 16px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        self.lbl_notice_title = QLabel("공지 제목")
        self.lbl_notice_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        c_layout.addWidget(self.lbl_notice_title)

        meta_layout = QHBoxLayout()
        self.lbl_notice_meta = QLabel("작성자: 영업지원팀 | 등록일: 2026-08-24 | 조회수: 1,428")
        self.lbl_notice_meta.setStyleSheet("font-size: 12px; color: #64748b;")
        meta_layout.addWidget(self.lbl_notice_meta)
        meta_layout.addStretch()
        c_layout.addLayout(meta_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e2e8f0;")
        c_layout.addWidget(line)

        self.txt_notice_body = QTextEdit()
        self.txt_notice_body.setReadOnly(True)
        self.txt_notice_body.setStyleSheet("border: none; font-size: 13px; line-height: 1.6; color: #334155;")
        c_layout.addWidget(self.txt_notice_body)

        # 첨부파일 영역
        attach_box = QFrame()
        attach_box.setStyleSheet("background: #f1f5f9; border-radius: 4px; padding: 8px;")
        a_layout = QHBoxLayout(attach_box)
        a_layout.addWidget(QLabel("📎 첨부파일: [LG_BEST_공식안내문_2026.pdf] (2.4MB)"))
        a_layout.addStretch()
        btn_dl = QPushButton("다운로드")
        btn_dl.setStyleSheet("padding: 4px 10px; background: #0284c7; color: white; border: none; border-radius: 3px;")
        a_layout.addWidget(btn_dl)
        c_layout.addWidget(attach_box)

        layout.addWidget(card)
        return widget

    def _show_notice_detail(self, title: str, date: str, category: str):
        self.lbl_notice_title.setText(f"[{category}] {title}")
        self.lbl_notice_meta.setText(f"작성부서: LG전자 B2B {category}팀  |  등록일자: {date}  |  조회수: 2,190회")

        body_html = (
            f"<h3>{title}</h3>"
            f"<p>안녕하십니까. 전국 LG전자 B2C/B2B 영업 파트너사 임직원 여러분.</p>"
            f"<p>본 공지는 <b>{date}</b> 부로 시행되는 신규 업무 가이드 및 현장 유의사항 안내입니다.</p>"
            f"<ul>"
            f"<li><b>적용 대상:</b> 전국 물류센터 및 직배송 전 권역</li>"
            f"<li><b>주요 개정 내용:</b> 현장 고객 협의 절차 강화 및 배송 지연 방지를 위한 사전 알림제 전면 도입</li>"
            f"<li><b>협조 요청:</b> 전 영업점 및 물류 담당자께서는 첨부된 공식 안내문과 매뉴얼을 필독하여 주시기 바랍니다.</li>"
            f"</ul>"
            f"<p>업무 중 문의사항이 있으실 경우 각 권역별 담당 SV 또는 시스템 Q&A 게시판을 활용해 주시기 바랍니다.<br>감사합니다.</p>"
        )
        self.txt_notice_body.setHtml(body_html)
        self.switch_page(8, f"https://newbest.lge.com/b2b/NEWBEST/board/noticeDetail.do?id=10842")

    def _create_page_header(self, breadcrumb: str, title: str) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        left_vbox = QVBoxLayout()
        lbl_bc = QLabel(breadcrumb)
        lbl_bc.setStyleSheet("font-size: 11px; color: #64748b;")
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        left_vbox.addWidget(lbl_bc)
        left_vbox.addWidget(lbl_t)
        header.addLayout(left_vbox)

        header.addStretch()

        btn_home = QPushButton("🏠 대시보드 홈으로")
        btn_home.setCursor(QCursor(Qt.PointingHandCursor))
        btn_home.setStyleSheet("""
            QPushButton {
                background-color: #212636;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border: 1px solid #373c4f;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #32384a;
                border-color: #e6004c;
            }
        """)
        btn_home.clicked.connect(self.go_dashboard_home)
        header.addWidget(btn_home)

        return header

    def _on_search_enter(self):
        query = self.txt_search.text().strip()
        if query:
            self.search_model_requested.emit(query)

    def _get_stylesheet(self) -> str:
        return """
        #LGErpMainView {
            background-color: #f0f2f5;
            font-family: 'Malgun Gothic', '맑은 고딕', sans-serif;
        }

        /* 0. 브라우저 URL 주소표시줄 */
        #BrowserUrlBar {
            background-color: #f1f5f9;
            border-bottom: 1px solid #cbd5e1;
        }

        #BrowserUrlLabel {
            font-size: 11px;
            color: #334155;
            font-family: 'Consolas', monospace;
        }

        /* 1. 최상단 탑바 */
        #TopBar {
            background-color: #1a1c24;
            border-bottom: 1px solid #111319;
        }

        #LogoBtn {
            background: transparent;
            border: none;
            color: #e6004c;
            font-size: 24px;
            font-weight: 900;
            font-family: 'Arial Black', sans-serif;
            letter-spacing: -0.5px;
            padding: 0;
            margin-right: 6px;
        }

        #LogoBtn:hover {
            color: #ff1a6b;
        }

        #SearchBox {
            background-color: #0f1015;
            border: 1px solid #323644;
            border-radius: 14px;
            height: 28px;
            min-width: 170px;
            max-width: 220px;
        }

        #SearchInput {
            background: transparent;
            border: none;
            color: #ffffff;
            font-size: 11px;
        }

        #SearchInput::placeholder {
            color: #888c9b;
        }

        #SearchBtn {
            background: transparent;
            border: none;
            color: #888c9b;
            font-size: 12px;
            padding: 0;
        }

        #UserNameLabel {
            color: #e2e4ea;
            font-size: 12px;
            font-weight: 500;
        }

        #TopIcon {
            color: #9ba1b0;
            font-size: 14px;
            padding: 0 4px;
        }

        #BestSecretaryBtn {
            background-color: #ffffff;
            color: #1a1c24;
            border: 1px solid #ffffff;
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: bold;
        }

        #BestSecretaryBtn:hover {
            background-color: #f0f0f0;
        }

        #TopToolBtn {
            background-color: #262a37;
            color: #d1d5db;
            border: 1px solid #373c4f;
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 11px;
        }

        #TopToolBtn:hover {
            background-color: #32384a;
            color: #ffffff;
        }

        /* 2. GNB 메뉴바 */
        #GnbBar {
            background-color: #212636;
            border-bottom: 2px solid #161a25;
        }

        #GnbMenuBtn {
            background: transparent;
            color: #ffffff;
            border: none;
            font-size: 13px;
            font-weight: bold;
            padding: 6px 4px;
        }

        #GnbMenuBtn:hover {
            color: #e6004c;
            background-color: #1a1e2c;
            border-radius: 4px;
        }

        /* ★ AI서비스 버튼 스타일 */
        #AiServiceBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d91b5c, stop:1 #8e2de2);
            color: #ffffff;
            border: 1px solid #ff4d88;
            border-radius: 14px;
            font-size: 12px;
            font-weight: 900;
            padding: 5px 14px;
            margin-left: 8px;
        }

        #AiServiceBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e6004c, stop:1 #a044ff);
            border: 1px solid #ffffff;
        }

        /* 3. 배너 컨테이너 */
        #BannerContainer {
            background-color: #ffffff;
            border: 1px solid #dcdfe6;
            border-radius: 4px;
        }

        /* 4. 오늘 꼭 해야 할 일 카드 */
        #TodoCard {
            background-color: #ffffff;
            border: 1px solid #dcdfe6;
            border-radius: 4px;
        }

        #TodoTitle {
            font-size: 13px;
            font-weight: bold;
            color: #1f2937;
        }

        #TodoClickItem {
            font-size: 12px;
            color: #1d4ed8;
            font-weight: 500;
        }

        #TodoClickItem:hover {
            text-decoration: underline;
            color: #2563eb;
        }

        #SubActionBtn {
            background: transparent;
            border: none;
            color: #2563eb;
            font-size: 11px;
            font-weight: bold;
        }

        #SubActionBtn:hover {
            text-decoration: underline;
        }

        /* 5. 공지사항 카드 */
        #NoticeCard {
            background-color: #ffffff;
            border: 1px solid #dcdfe6;
            border-radius: 4px;
        }

        #NoticeTitle {
            font-size: 13px;
            font-weight: bold;
            color: #1f2937;
        }

        #NoticeTabActive {
            background: transparent;
            border: none;
            font-size: 12px;
            font-weight: bold;
            color: #1f2937;
            text-decoration: underline;
        }

        #NoticeTab {
            background: transparent;
            border: none;
            font-size: 12px;
            color: #6b7280;
        }

        #NoticeTab:hover {
            color: #1f2937;
        }

        #NoticeMoreBtn {
            background: transparent;
            border: none;
            font-size: 11px;
            color: #6b7280;
        }

        #NoticeMoreBtn:hover {
            color: #1f2937;
        }

        #NoticeCategory {
            font-size: 11px;
            color: #1f2937;
            font-weight: 500;
        }

        #NoticeItemTitle {
            font-size: 11px;
            color: #374151;
        }

        #NoticeItemTitle:hover {
            color: #1d4ed8;
            text-decoration: underline;
        }

        #NoticeHighlightTitle {
            font-size: 11px;
            color: #d81a50;
            font-weight: bold;
        }

        #NoticeHighlightTitle:hover {
            color: #b91c1c;
            text-decoration: underline;
        }

        #NoticeDate {
            font-size: 11px;
            color: #6b7280;
        }

        #NoticeDateHighlight {
            font-size: 11px;
            color: #d81a50;
            font-weight: bold;
        }

        /* 서브 페이지 공통 스타일 */
        #FilterFrame {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 8px 12px;
        }

        #PrimaryActionBtn {
            background-color: #0284c7;
            color: white;
            font-weight: bold;
            border-radius: 4px;
            padding: 6px 14px;
            border: none;
        }

        #PrimaryActionBtn:hover {
            background-color: #0369a1;
        }

        QTableWidget {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            gridline-color: #e2e8f0;
            font-size: 12px;
        }

        QHeaderView::section {
            background-color: #f8fafc;
            color: #334155;
            font-weight: bold;
            border: 1px solid #e2e8f0;
            padding: 6px;
        }
        """
