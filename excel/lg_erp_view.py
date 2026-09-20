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
)


def resource_path(relative_path: str) -> str:
    """PyInstaller 실행 환경 및 개발 환경 모두 지원하는 경로 반환"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class LGErpMainView(QWidget):
    """
    LG B2B ERP (NEW BEST) 메인 화면 클론 뷰 위젯.
    'AI서비스' 버튼 클릭 시 ai_service_clicked 시그널을 방출합니다.
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

        # 1. 최상단 탑바 (Top Bar)
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        # 2. GNB 네비게이션 메뉴바
        gnb_bar = self._create_gnb_bar()
        main_layout.addWidget(gnb_bar)

        # 3. 본문 스크롤 영역 (창 크기가 작아져도 자연스럽게 대응)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(10)

        # 3-1. 히어로 배너 영역
        banner_widget = self._create_hero_banner()
        content_layout.addWidget(banner_widget)

        # 3-2. 오늘 꼭 해야 할 일 섹션
        todo_widget = self._create_todo_section()
        content_layout.addWidget(todo_widget)

        # 3-3. 하단 2분할 공지사항 섹션 (영업공지사항 & 전산공지사항)
        notices_widget = self._create_notices_section()
        content_layout.addWidget(notices_widget)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        self.setStyleSheet(self._get_stylesheet())

    def _create_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(44)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # 좌측 BEST 로고
        lbl_logo = QLabel("BEST")
        lbl_logo.setObjectName("LogoLabel")
        layout.addWidget(lbl_logo)

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
        layout.addWidget(btn_secretary)

        btn_quick = QPushButton("★ 퀵메뉴")
        btn_quick.setObjectName("TopToolBtn")
        btn_quick.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(btn_quick)

        btn_link = QPushButton("🔗 링크")
        btn_link.setObjectName("TopToolBtn")
        btn_link.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(btn_link)

        btn_collapse = QPushButton("☰ 메뉴접기")
        btn_collapse.setObjectName("TopToolBtn")
        btn_collapse.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(btn_collapse)

        btn_org = QPushButton("👥 조직전환")
        btn_org.setObjectName("TopToolBtn")
        btn_org.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(btn_org)

        btn_mail = QLabel("✉️")
        btn_mail.setObjectName("TopIcon")
        layout.addWidget(btn_mail)

        btn_logout = QLabel("🚪")
        btn_logout.setObjectName("TopIcon")
        layout.addWidget(btn_logout)

        return bar

    def _create_gnb_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("GnbBar")
        bar.setFixedHeight(38)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(40, 0, 40, 0)
        layout.setSpacing(4)

        menus = ["마스터", "납품/인사", "구매/환입", "재고/이관", "판매/배송", "결산/LGE거래"]
        for menu_name in menus:
            btn = QPushButton(menu_name)
            btn.setObjectName("GnbMenuBtn")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            layout.addWidget(btn, 1)

        # ★ 핵심 요구사항: "AI서비스" 버튼 추가!
        self.btn_ai_service = QPushButton("✨ AI서비스 (엑셀 가격표)")
        self.btn_ai_service.setObjectName("AiServiceBtn")
        self.btn_ai_service.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_ai_service.setToolTip("클릭하여 엑셀 가격표 할인율 조정기로 진입합니다")
        self.btn_ai_service.clicked.connect(self.ai_service_clicked.emit)
        layout.addWidget(self.btn_ai_service, 1)

        return bar

    def _create_hero_banner(self) -> QWidget:
        container = QFrame()
        container.setObjectName("BannerContainer")
        container.setFixedHeight(215)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 추출된 고해상도 배너 이미지 로드
        banner_img_path = resource_path("banner_hero.png")
        lbl_banner = QLabel()
        lbl_banner.setObjectName("BannerImageLabel")
        lbl_banner.setAlignment(Qt.AlignCenter)

        if os.path.exists(banner_img_path):
            pix = QPixmap(banner_img_path)
            # 화면 비율 유지하며 스케일
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
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 항목들 (가로 2열 배치)
        items_layout = QHBoxLayout()
        items_layout.setSpacing(40)

        # 1열
        col1_layout = QVBoxLayout()
        col1_layout.setSpacing(6)
        item1 = QLabel("✔  전일대비 약속일 변경건")
        item1.setObjectName("TodoItem")
        item2 = QLabel("✔  자동 적자 예상건")
        item2.setObjectName("TodoItem")
        col1_layout.addWidget(item1)
        col1_layout.addWidget(item2)
        items_layout.addLayout(col1_layout)

        # 2열
        col2_layout = QVBoxLayout()
        col2_layout.setSpacing(6)
        item3 = QLabel("✔  당일 배송 예정건")
        item3.setObjectName("TodoItem")
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

        # 1. 영업공지사항 카드
        sales_card = self._create_sales_notices()
        layout.addWidget(sales_card, 1)

        # 2. 전산공지사항 카드
        it_card = self._create_it_notices()
        layout.addWidget(it_card, 1)

        return container

    def _create_sales_notices(self) -> QWidget:
        card = QFrame()
        card.setObjectName("NoticeCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # 탭 헤더
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
        tab_layout.addWidget(btn_more)

        layout.addLayout(tab_layout)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(line)

        # 공지사항 목록
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

            lbl_title = QLabel(title)
            lbl_title.setObjectName("NoticeHighlightTitle" if is_highlight else "NoticeItemTitle")
            lbl_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
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

        # 탭 헤더
        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(12)

        lbl_title = QLabel("전산공지사항")
        lbl_title.setObjectName("NoticeTitle")
        tab_layout.addWidget(lbl_title)

        tab_layout.addStretch()

        btn_more = QPushButton("+ 더보기")
        btn_more.setObjectName("NoticeMoreBtn")
        tab_layout.addWidget(btn_more)

        layout.addLayout(tab_layout)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(line)

        # 공지사항 목록
        notices = [
            ("[New BEST] 출하보류 해지요청 메일발송 기능 반영 (2026-08-25)", "2026-08-25", True),
            ("[New BEST] LGE 주문 조회 화면 변경사항 안내(2026-08-19)", "2026-08-19", False),
            ("[New BEST] 알림 기능 파일럿 운영 - 신고확인서 알림", "2026-08-05", False),
            ("[안내] New BEST 세션타임아웃 시간 변경 건", "2026-08-03", False),
        ]

        for title, date, is_highlight in notices:
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl_title = QLabel(title)
            lbl_title.setObjectName("NoticeHighlightTitle" if is_highlight else "NoticeItemTitle")
            lbl_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(lbl_title, 1)

            lbl_date = QLabel(date)
            lbl_date.setObjectName("NoticeDateHighlight" if is_highlight else "NoticeDate")
            row.addWidget(lbl_date)

            layout.addLayout(row)

        layout.addStretch()
        return card

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

        #ContentWidget {
            background-color: #f0f2f5;
        }

        /* 1. 최상단 탑바 */
        #TopBar {
            background-color: #1a1c24;
            border-bottom: 1px solid #111319;
        }

        #LogoLabel {
            color: #e6004c;
            font-size: 24px;
            font-weight: 900;
            font-family: 'Arial Black', sans-serif;
            letter-spacing: -0.5px;
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

        #TodoItem {
            font-size: 12px;
            color: #4b5563;
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

        #NoticeHighlightTitle {
            font-size: 11px;
            color: #d81a50;
            font-weight: bold;
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
        """
