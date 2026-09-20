from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Tuple
import math

import requests
from urllib.parse import quote_plus

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font

from excel_price_tables import TableRegion


def refine_search_keyword(model: str) -> str:
    """
    사용자가 요청한 6가지 다나와 검색어 치환 규칙을 적용합니다.
    [대전제] 모델명에 '.'이 포함된 경우, '.' 앞부분만 추출합니다.
    1. '**' 포함 시: 바로 앞 한 글자와 함께 공백으로 치환
    2. '*' 포함 시: 바로 앞 한 글자와 함께 공백으로 치환 (1번 적용 후 남은 것)
    3. 'OLED' 포함 & 끝에 'S/W' 시: 'S/W'를 'NA'로 치환
    4. 'QNED' 포함 & 끝에 'W'나 'S' 시: 'W'/'S'를 'A'로 치환
    5. 'OLED' 미포함 & 끝에 'S/W' 시: 'S/W'를 'A'로 치환
    6. 끝에 'G/W' 시: '/W'를 'NA'로 치환
    """
    if not model or not model.strip():
        return ""
        
    keyword = model.strip()
    
    # [대전제] 모델명에 '.'이 포함된 경우, '.' 앞부분만 추출하여 나머지 조건을 쳐냅니다.
    if "." in keyword:
        keyword = keyword.split(".")[0]
        
    # 1. 모델명에 "**"이 포함된 경우, 바로 앞 한 글자와 함께 공백으로 치환
    # 정규식 .\*\* 는 (임의의한글자)** 를 매칭합니다.
    if "**" in keyword:
        keyword = re.sub(r'.\*\*', ' ', keyword)
        
    # 2. 모델명에 "*"이 포함된 경우 (,** 제외), 바로 앞 한 글자와 함께 공백으로 치환
    if "*" in keyword:
        keyword = re.sub(r'.\*', ' ', keyword)
        
    is_oled = "OLED" in keyword.upper()
    is_qned = "QNED" in keyword.upper()
    
    # 3. 'OLED' 포함 & 끝에 'S/W'가 있을 경우 'S/W'를 'NA'로 대체
    if is_oled and keyword.upper().endswith("S/W"):
        # rstrip 대신 슬라이싱으로 정확히 끝의 3글자를 치환
        keyword = keyword[:-3] + "NA"
        
    # 4. 'QNED' 포함인 경우 (끝이 S/W, 1/2, W, S 순으로 확인)
    elif is_qned:
        upper_kw = keyword.upper()
        if upper_kw.endswith("S/W"):
            keyword = keyword[:-3] + "A"
        elif upper_kw.endswith("1/2"):
            keyword = keyword[:-3] + "A"
        elif upper_kw.endswith("W") or upper_kw.endswith("S"):
            keyword = keyword[:-1] + "A"
        
    # 5. 'OLED' 미포함 & 끝에 'S/W'가 있을 경우 'A'로 대체
    elif not is_oled and keyword.upper().endswith("S/W"):
        keyword = keyword[:-3] + "A"
        
    # 6. 끝에 'G/W'가 있을 경우 '/W' 부분만 'NA'로 대체 (결과적으로 GNA)
    if keyword.upper().endswith("G/W"):
        keyword = keyword[:-2] + "NA"
        
    # 불필요한 연속 공백 제거
    keyword = re.sub(r'\s+', ' ', keyword).strip()
    return keyword


def fetch_danawa_lowest_price(model: str, *, timeout: float = 6.0) -> Tuple[Optional[int], str, str]:
    """
    다나와 통합검색에서 해당 모델 문자열로 검색해,
    사용자가 지정한 패턴(모델명 포함, 별점 존재, 판매몰 30개 이상)을 만족하는 상품 중 최저가를 찾습니다.
    """
    if not model or model.strip() == "":
        return None, "", ""

    search_keyword = refine_search_keyword(model)
    if not search_keyword:
        return None, "", ""

    query = quote_plus(search_keyword)
    url = f"https://search.danawa.com/dsearch.php?query={query}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception:
        return None, search_keyword, url

    if resp.status_code != 200:
        return None, search_keyword, url

    if BeautifulSoup is None:
        raise RuntimeError("BeautifulSoup (bs4) is not installed. Please install it using 'pip install beautifulsoup4'.")

    # BeautifulSoup을 이용해 HTML 구조 파싱 (사용자 지정 조건 적용)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    items = soup.select('li.prod_item')
    valid_prices = []
    
    # 예외/Fallback 용도: 조건에 하나도 안 맞을 경우를 대비해 최상단 상품 가격 임시 저장
    fallback_price = None

    for item in items:
        name_elem = item.select_one('.prod_name a')
        if not name_elem:
            continue
        prod_name = name_elem.text.strip()
        prod_normalized = prod_name.lower().replace(" ", "")
        search_terms = search_keyword.lower().split()
        
        # Fallback 가격 캐싱 (광고/일반 상관없이 제일 먼저 보이는 가격 중 검색어가 조금이라도 매칭되는 첫번째 상품)
        if fallback_price is None:
            # 완전 엉뚱한 필터나 부품 등 제외
            first_term = search_terms[0] if search_terms else ""
            if first_term and first_term in prod_normalized:
                first_price_elem = item.select_one('.price_sect strong')
                if first_price_elem:
                    try:
                        fallback_price = int(first_price_elem.text.replace(',', ''))
                    except ValueError:
                        pass
        
        # 조건 1: 상품명 일치 (검색어 띄어쓰기 기준 AND 매칭)
        # 검색어 내 모든 단어가(대소문자 무시) 상품명에 모두 포함되어야 함
        all_terms_matched = True
        for term in search_terms:
            if term not in prod_normalized:
                all_terms_matched = False
                break
                
        if not all_terms_matched:
            continue
            
        # 조건 2: 별점이 존재해야 함
        has_rating = False
        star = item.find(string=lambda t: t and '별점' in t)
        if star:
            has_rating = True
            
        # 조건 3: 판매몰 갯수가 30개 이상이어야 함
        mall_count = 0
        for t in item.find_all(string=True):
            s = t.strip()
            if s.endswith('몰'):
                m = re.search(r'(\d+)몰', s)
                if m:
                    mall_count = max(mall_count, int(m.group(1)))
                    
        # 3가지 조건 모두 만족 시 우측의 가장 싼 가격 수집
        if has_rating and mall_count >= 30:
            item_prices = []
            
            # 비교리스트 방식이 있는 경우 하위 가격들 수집
            price_list = item.select('.item_info li .price_sect strong')
            if price_list:
                for pe in price_list:
                    try:
                        item_prices.append(int(pe.text.replace(',', '')))
                    except ValueError:
                        pass
            else:
                # 일반 뷰
                for pe in item.select('.price_sect strong'):
                    try:
                        item_prices.append(int(pe.text.replace(',', '')))
                    except ValueError:
                        pass
                        
            if item_prices:
                valid_prices.append(min(item_prices))

    if valid_prices:
        # 조건에 맞는 상품들 중에서 최저가 반환
        return min(valid_prices), search_keyword, url
    elif fallback_price is not None:
        # 조건을 완벽히 만족하는 건 없지만 아예 매칭 안되는 건 아닐 때의 차선책
        return fallback_price, search_keyword, url
    
    return None, search_keyword, url


def build_price_map(models: Iterable[str]) -> Dict[str, Tuple[Optional[int], str, str]]:
    """
    여러 모델 문자열에 대해 다나와 최저가를 조회합니다.
    - 중복 모델은 한 번만 조회.
    """
    result: Dict[str, Tuple[Optional[int], str, str]] = {}
    for m in set(s for s in models if s and s.strip()):
        result[m] = fetch_danawa_lowest_price(m)
    return result


def write_price_comparison(
    ws: Worksheet,
    tables: Iterable[TableRegion],
    price_map: Dict[str, Tuple[Optional[int], str, str]],
) -> None:
    """
    각 테이블/행의 모델명을 기준으로 다나와 최저가와 공급가를 비교해
    시트의 끝부분에 열을 추가하고 가격 경쟁력 여부를 표시합니다.
    (적용된 검색어 및 결과 링크도 함께 출력합니다)

    - 열 이름: '다나와 최저가', '가격 비교', '검색어', '링크'
    - 공급가 <= 다나와 최저가 이면 '경쟁력 有' 텍스트를 빨간색으로 표시.
    """
    max_col = ws.max_column or 0

    danawa_col = max_col + 1
    compare_col = max_col + 2
    diff_amt_col = max_col + 3
    diff_pct_col = max_col + 4
    keyword_col = max_col + 5
    link_col = max_col + 6

    # 각 테이블 헤더 행에 제목 입력
    for t in tables:
        ws.cell(row=t.header_row, column=danawa_col).value = "다나와 최저가"
        ws.cell(row=t.header_row, column=compare_col).value = "가격 비교"
        ws.cell(row=t.header_row, column=diff_amt_col).value = "차액 (공급가-최저가)"
        ws.cell(row=t.header_row, column=diff_pct_col).value = "차이(%)"
        ws.cell(row=t.header_row, column=keyword_col).value = "검색어"
        ws.cell(row=t.header_row, column=link_col).value = "검색 결과 링크"

    red_font = Font(color="FFFF0000")
    blue_link_font = Font(color="FF0000FF", underline="single") # 하이퍼링크 스타일
    blue_text_font = Font(color="FF0000FF") # 경쟁력 보통 텍스트용

    for t in tables:
        for r in range(t.first_data_row, t.last_data_row + 1):
            model_v = ws.cell(row=r, column=t.col_model).value
            if not isinstance(model_v, str) or not model_v.strip():
                continue
            model = model_v.strip()

            result = price_map.get(model)
            if not result:
                continue
                
            market_price, search_keyword, url = result

            # 검색어 및 링크 입력
            if search_keyword:
                ws.cell(row=r, column=keyword_col).value = search_keyword
            if url:
                link_cell = ws.cell(row=r, column=link_col)
                link_cell.value = "결과 바로가기"
                link_cell.hyperlink = url
                link_cell.font = blue_link_font

            if market_price is None:
                continue

            ws.cell(row=r, column=danawa_col).value = market_price

            supply_v = ws.cell(row=r, column=t.col_supply).value
            try:
                supply = float(str(supply_v).replace(",", "")) if supply_v is not None else None
            except ValueError:
                supply = None

            if supply is None:
                continue

            # 차액 및 차이(%) 계산
            diff_amt = supply - market_price
            diff_pct = (diff_amt / market_price * 100) if market_price > 0 else 0
            
            # 셀 객체 가져오기
            comp_cell = ws.cell(row=r, column=compare_col)
            diff_amt_cell = ws.cell(row=r, column=diff_amt_col)
            diff_pct_cell = ws.cell(row=r, column=diff_pct_col)
            
            # 값 할당
            diff_amt_cell.value = diff_amt
            # 엑셀 숫자 서식 (#,##0)
            diff_amt_cell.number_format = '#,##0'
            diff_pct_cell.value = f"{diff_pct:.1f}%"

            # 1. 내 공급가가 다나와 가격보다 무조건 싼 경우 -> '경쟁력 有' (빨간색)
            if supply < market_price:
                comp_cell.value = "경쟁력 有"
                comp_cell.font = red_font
                diff_amt_cell.font = red_font
                diff_pct_cell.font = red_font
            # 2. 내 공급가가 다나와 가격과 같거나 5% 이내로 비싼 경우 -> '경쟁력 보통' (파란색)
            elif supply <= market_price * 1.05:
                comp_cell.value = "경쟁력 보통"
                comp_cell.font = blue_text_font
                diff_amt_cell.font = blue_text_font
                diff_pct_cell.font = blue_text_font
            # 3. 내 공급가가 다나와 가격보다 5% 넘게 비싼 경우 -> '경쟁력 미흡' (일반)
            else:
                comp_cell.value = "경쟁력 미흡"
