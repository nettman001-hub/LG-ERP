import logging
import os
import requests
import time
import re
from collections import OrderedDict
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin

logger = logging.getLogger(__name__)
DEBUG_LOGS_ENABLED = os.environ.get("ERP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _debug_print(*args, **kwargs) -> None:
    if DEBUG_LOGS_ENABLED:
        print(*args, **kwargs)

B2B_FORM_KEYS = [
    "TOKEN",
    "ACTIVE_MODE",
    "B2C_CALLBACK_URL",
    "B2B_CALLBACK_URL",
    "isCompPopup",
    "TARGET_URL",
    "userName",
    "compCode",
    "LINK_DIV",
    "LINK_URL",
    "FORM_YN",
]


@dataclass(frozen=True)
class ProductionPlanDay:
    day_code: str
    plan_qty: int
    promised_qty: int
    available_qty: int


@dataclass(frozen=True)
class ProductionPlanResult:
    plan_total: int = 0
    promised_total: int = 0
    available_weekly_total: int = 0
    available_total: int = 0
    days: tuple[ProductionPlanDay, ...] = ()


@dataclass(frozen=True)
class InventoryLookupResult:
    model: dict
    inventory_rows: list[dict]
    inventory_total: int
    inventory_error: str
    production_plan: ProductionPlanResult
    production_error: str
    score: int
    selection_note: str = ""


def normalize_model_prefix(value: str) -> str:
    raw = (value or "").strip().upper()
    if not raw:
        return ""
    return re.sub(r"[^A-Z0-9]", "", raw.split(".", 1)[0])


def filter_exact_prefix_models(query: str, models: list[dict]) -> list[dict]:
    target = normalize_model_prefix(query)
    if not target:
        return []

    filtered: list[dict] = []
    for model in models:
        item_cd = str(model.get("ITEM_CD", "")).strip()
        if normalize_model_prefix(item_cd) == target:
            filtered.append(model)
    return filtered


def _format_day_code(day_code: str) -> str:
    """D01 ?�태??day code�?D+01 ?�태�?변?�합?�다."""
    m = re.match(r'^([A-Za-z]+)(\d+)$', day_code)
    if m:
        return f"{m.group(1)}+{m.group(2)}"
    return day_code


def format_production_plan_details(plan: ProductionPlanResult) -> list[str]:
    lines: list[str] = []
    for day in plan.days:
        code = _format_day_code(day.day_code)
        lines.append(
            f"{code}: ?�산계획 {day.plan_qty} / "
            f"?�기?�속???�산계획 {day.promised_qty} / "
            f"?�기?�속 가???�산계획 {day.available_qty}"
        )
    return lines


def extract_hidden_inputs(html_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not html_text:
        return values

    for tag in re.findall(r"<input\b[^>]*>", html_text, flags=re.IGNORECASE):
        type_match = re.search(r'type\s*=\s*["\']?([^"\'>\s]+)', tag, flags=re.IGNORECASE)
        if not type_match or type_match.group(1).lower() != "hidden":
            continue

        name_match = re.search(r'name\s*=\s*["\']?([^"\'>\s]+)', tag, flags=re.IGNORECASE)
        if not name_match:
            continue

        value_match = re.search(r'value\s*=\s*["\']([^"\']*)["\']', tag, flags=re.IGNORECASE)
        name = unescape(name_match.group(1))
        value = unescape(value_match.group(1)) if value_match else ""
        values[name] = value

    return values


def extract_b2b_form_fields(html_text: str) -> dict[str, str]:
    values = extract_hidden_inputs(html_text)
    result: dict[str, str] = {}

    for key in B2B_FORM_KEYS:
        if key in values:
            result[key] = values[key]

    for key in B2B_FORM_KEYS:
        if key in result:
            continue
        match = re.search(
            rf"\b(?:var\s+)?{re.escape(key)}\b\s*=\s*[\"']([^\"']*)[\"']",
            html_text,
            flags=re.IGNORECASE,
        )
        if match:
            result[key] = unescape(match.group(1))

    return result

class NexacroSSVParser:
    """Nexacro SSV ?�답 ?�맷???�싱?�는 ?�래??""
    
    RS = '\x1E'  # Record Separator (ASCII 30) - ??구분??
    US = '\x1F'  # Unit Separator (ASCII 31) - ??구분??
    NULL_CHAR = '\x03' # Null Value (ASCII 3)

    @staticmethod
    def parse_ssv_variables(text: str) -> dict[str, str]:
        """
        SSV ?�단 변??ErrorCode/ErrorMsg ??�??�싱?�여 {?? �? ?�태�?반환
        """
        variables: dict[str, str] = {}
        if not text or not text.startswith("SSV:utf-8"):
            return variables

        for line in text.split(NexacroSSVParser.RS)[1:]:
            if not line or line.startswith("Dataset:"):
                continue
            if "=" not in line:
                continue

            left, right = line.split("=", 1)
            key = left.split(":", 1)[0].strip()
            if not key:
                continue

            value = "" if right == NexacroSSVParser.NULL_CHAR else right
            variables[key] = value

        return variables
    
    @staticmethod
    def parse_ssv_response(text: str) -> dict[str, list[dict]]:
        """
        SSV ?�스?��? ?�싱?�여 {?�이?�셋�? [???�이???�셔?�리, ...]} ?�태�?반환
        """
        datasets = {}
        
        if not text or not text.startswith("SSV:utf-8"):
            return datasets
            
        # ?�이?�셋 블록 분리 (Dataset: ?�로 ?�작?�는 부분들)
        parts = text.split("Dataset:")
        
        for part in parts[1:]: # �?번째 부분�? SSV ?�더?��?�??�략
            lines = part.split(NexacroSSVParser.RS)
            if not lines:
                continue
                
            # �?번째 ?�인?� ?�이?�셋 ?�름 �?컬럼 ?�보
            header_str = lines[0].strip()
            if not header_str:
                continue
                
            header_parts = header_str.split(NexacroSSVParser.US)
            dataset_name = header_parts[0]
            
            # _Const_ 변?�들?� ?�외?�고 ?�제 컬럼 ?�의�?추출 (_RowType_ ???�수 컬럼??존재)
            # ?�기?�는 ?�순??_RowType_ ?�음부???�는 컬럼명들??추출?�는 방식 ?�용
            columns = []
            if len(lines) > 1:
                # ??번째 ?�인??_ColumnInfo_ ?�의
                col_info_str = lines[1]
                if col_info_str.startswith(("_ColumnInfo_", "_RowType_")):
                    cols = col_info_str.split(NexacroSSVParser.US)[1:]
                    for c in cols:
                        if c:
                            # 컬럼�??�???�기 추출 (?? ITEM_CD:STRING:256)
                            col_name = c.split(":")[0]
                            columns.append(col_name)
                    
                    # ??번째 ?�인부???�제 ?�이??(Normal, Insert, Update ??RowType?�로 ?�작)
                    rows = []
                    for line in lines[2:]:
                        if not line.strip():
                            continue
                        
                        values = line.split(NexacroSSVParser.US)
                        if len(values) > 0 and values[0] in ('N', 'I', 'U', 'D'):
                            # RowType 컬럼(N, I, ???� 건너?�고 �?매핑
                            row_data = {}
                            val_idx = 1
                            for col_name in columns:
                                if val_idx < len(values):
                                    val = values[val_idx]
                                    # null 문자 처리
                                    if val == NexacroSSVParser.NULL_CHAR:
                                        val = ""
                                    row_data[col_name] = val
                                else:
                                    row_data[col_name] = ""
                                val_idx += 1
                            rows.append(row_data)
                    datasets[dataset_name] = rows        
        return datasets

class SSVPayloadBuilder:
    """Nexacro SSV ?�태???�청 ?�이?��? ?�성?�는 ?�래??""
    
    RS = '\x1E'
    US = '\x1F'
    NULL_CHAR = '\x03'
    
    @staticmethod
    def build_payload(
        datasets: dict,
        variables: dict = None,
        null_for_empty: bool = True,
    ) -> str:
        """
        datasets ?�셔?�리?� variables ?�셔?�리�??�력받아 SSV 문자?�로 직렬??
        ?�태: variables + { "DatasetName": {"columns": ["�?", "�?"], "rows": [["�?", "�?"], ...]} }
        """
        result = "SSV:utf-8" + SSVPayloadBuilder.RS
        
        if variables:
            for k, v in variables.items():
                result += f"{k}={v}" + SSVPayloadBuilder.RS
                
        for ds_name, ds_info in datasets.items():
            result += f"Dataset:{ds_name}" + SSVPayloadBuilder.RS
            
            columns = ds_info.get("columns", [])
            if not columns:
                continue
                
            # 컬럼 ?�보 조립 (?�의�?STRING:256?�로 ?�일, ?�요???�장)
            col_info = "_RowType_" + SSVPayloadBuilder.US
            col_info += SSVPayloadBuilder.US.join([f"{col}:STRING(256)" for col in columns])
            result += col_info + SSVPayloadBuilder.RS
            
            # ?�이??로우 조립 (Normal ?�성 'N'??붙여???�송)
            rows = ds_info.get("rows", [])
            for row in rows:
                row_str = "N" + SSVPayloadBuilder.US
                # �?값�? NULL_CHAR ?�는 �?문자??처리
                formatted_values = []
                for value in row:
                    if value is None:
                        formatted_values.append(SSVPayloadBuilder.NULL_CHAR)
                    elif value == "":
                        formatted_values.append(
                            SSVPayloadBuilder.NULL_CHAR if null_for_empty else ""
                        )
                    else:
                        formatted_values.append(str(value))
                row_str += SSVPayloadBuilder.US.join(formatted_values)
                result += row_str + SSVPayloadBuilder.RS

            # Nexacro requests separate dataset blocks with an empty record.
            result += SSVPayloadBuilder.RS

        return result

class ERPSession:
    """브라?��? ?�어 ?�??requests�??�용??백그?�운???�션 �?API ?�증 관�?""
    def __init__(self):
        self.session = requests.Session()
        # SSL 검�?비활?�화 (LGE ?�내 CA�?Python???�뢰?��? ?�기 ?�문)
        self.session.verify = False
        # urllib3 SSL 경고 ?�제
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # 기본 ?�더 ?�정 (?�용??브라?��??� ?�일?�게 맞춤)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
            "Accept": "text/html, application/xhtml+xml, image/jxr, */*",
            "Accept-Language": "ko-KR",
            "Connection": "Keep-Alive"
        })
        self.user_id: str | None = None
        self.password: str | None = None
        self.internal_user_id: str | None = None
        self.user_id_candidates: list[str] = []
        self.employee_ssn: str | None = None
        self.channel_code: str = "HPZ_CNJ"
        self.comp_code: str = "1"
        self.inventory_wh_id: str = "4"
        self.b2b_bridge_form: dict[str, str] = {}
        self._logged_in = False
        self.last_activity_time: float = 0.0  # 마�?�?ERP ?�속 ?�각 (time.time())

        # ?�증 ?�로??�??��????�태 ?�??
        self._pre_step_token = ""
        self._user_hp_no = ""
        self._opt_key = ""
        self._comp_type = "E"
        
    def is_session_valid(self) -> bool:
        return self._logged_in and bool(self.user_id)

    def touch_activity(self) -> None:
        """마�?�??�속 ?�각???�재 ?�각?�로 갱신?�니??"""
        self.last_activity_time = time.time()

    def keep_alive(self) -> bool:
        """Portal �?B2B ?�버??가벼운 GET ?�청??보내 ?�션???��??�니??

        Returns:
            True  - ?�청 ?�공 (2xx)
            False - 미로그인 ?�태?�거???�청 ?�패
        """
        if not self.is_session_valid():
            return False

        base_url = "https://newbest.lge.com"
        try:
            res_portal = self.session.get(
                f"{base_url}/cm/portal/index.do",
                timeout=10,
            )
            _debug_print(f"[KEEPALIVE] portal index.do status={res_portal.status_code}")

            res_b2b = self.session.get(
                f"{base_url}/b2b/NEWBEST/index.jsp",
                timeout=10,
            )
            _debug_print(f"[KEEPALIVE] b2b index.jsp status={res_b2b.status_code}")

            self.touch_activity()
            return res_portal.status_code < 400
        except Exception as e:
            logger.warning(f"[KEEPALIVE] ?�션 ?��? ?�청 ?�패: {e}")
            return False

    def login_step1_request_sms(self, user_id: str, password: str) -> bool:
        """
        [STEP 1] index.do ?�속 ??preLogin.do ?�출?�여 SMS ?�증번호�?발송?�니??
        ?�공 ??True�?반환?�며, ?�업?�서 ?�증번호 ?�력???�기하�??�니??
        """
        self.user_id = user_id.upper()
        self.password = password
        
        base_url = "https://newbest.lge.com"
        
        try:
            # 1. 메인 ?�이지 ?�근?�여 초기 쿠키 ?�득
            res_index = self.session.get(f"{base_url}/cm/portal/index.do", timeout=10)
            _debug_print(f"[DEBUG] index.do status={res_index.status_code}, cookies={dict(self.session.cookies)}")
            
            # 2. preLogin.do ?�출 (isPreStep ???�보 ?�득)
            self.session.headers.update({
                "Referer": f"{base_url}/cm/portal/index.do",
                "Content-Type": "application/x-www-form-urlencoded"
            })
            prelogin_payload = {
                "USER_NM": self.user_id,
                "PASSWORD": self.password,
                "eCatalogUrl": "",
                "eCatalogFlag": "",
                "linkGubun": "",
                "saveId": "1"
            }
            res = self.session.post(f"{base_url}/cm/portal/preLogin.do", data=prelogin_payload, timeout=10)
            _debug_print(f"[DEBUG] preLogin.do status={res.status_code}")
            _debug_print(f"[DEBUG] preLogin.do response text (first 500):\n{res.text[:500]}")
            
            try:
                data = res.json()
            except Exception as json_err:
                logger.error(f"preLogin ?�답??JSON???�닙?�다: {json_err}")
                _debug_print(f"[DEBUG] preLogin response full:\n{res.text[:1000]}")
                return False
            
            _debug_print(f"[DEBUG] preLogin.do JSON: {data}")
            
            if data.get("msgCd") != "0":
                logger.error(f"preLogin ?�패: msgCd={data.get('msgCd')}, msg={data.get('msg')}")
                return False
                
            self.employee_ssn = data.get("ssn", "") or None
            self._pre_step_token = data.get("isPreStep", "")
            self._comp_type = data.get("compType", "E")
            self.comp_code = data.get("compCode", "1") or "1"
            mobile_no = data.get("mobileNo", "")
            self._user_hp_no = mobile_no.replace("-", "") if mobile_no else ""
            
            is_phone_certi = data.get("isPhoneCerti", "N")
            _debug_print(f"[DEBUG] isPhoneCerti={is_phone_certi}, mobileNo={mobile_no}, compType={self._comp_type}")
            
            if is_phone_certi != "Y":
                logger.error("?��????�증 ?�?�이 ?�닙?�다.")
                return False
            if not self._user_hp_no:
                logger.error("?��???번호 ?�보가 ?�습?�다.")
                return False

            # 3. SMS ?�증번호 발송 ?�청
            sms_payload = {
                "userNm": self.user_id,
                "userHpNo": self._user_hp_no,
                "compType": self._comp_type,
                "smsType": "L"
            }
            _debug_print(f"[DEBUG] smsSend.do payload: {sms_payload}")
            res_sms = self.session.post(f"{base_url}/cm/sms/smsSend.do", data=sms_payload, timeout=10)
            _debug_print(f"[DEBUG] smsSend.do status={res_sms.status_code}")
            _debug_print(f"[DEBUG] smsSend.do response text (first 500):\n{res_sms.text[:500]}")
            
            try:
                sms_data = res_sms.json()
            except Exception as json_err:
                logger.error(f"smsSend ?�답??JSON???�닙?�다: {json_err}")
                return False
            
            _debug_print(f"[DEBUG] smsSend.do JSON: {sms_data}")
            
            err_code = sms_data.get("errCode", "")
            if err_code == "F":
                logger.error(f"SMS 발송 ?�패: {sms_data.get('errMsg', '?????�는 ?�류')}")
                return False
            else:
                self._opt_key = sms_data.get("optKey", "")
                logger.info(f"SMS 발송 ?�공. optKey={self._opt_key}")
                return True
                
        except Exception as e:
            logger.error(f"login_step1 ?�러: {e}")
            import traceback
            traceback.print_exc()
            return False

    def login_step2_verify_sms(self, otp_code: str) -> bool:
        """Verify the SMS OTP and establish the portal session."""
        from urllib.parse import quote

        base_url = "https://newbest.lge.com"
        encoded_opt_key = quote(self._opt_key, safe="")

        verify_payload = {
            "optKey": encoded_opt_key,
            "optCode": otp_code,
            "userNm": self.user_id,
            "userHpNo": self._user_hp_no,
        }
        _debug_print(f"[DEBUG] smsOptCheck payload: {verify_payload}")
        _debug_print(f"[DEBUG] otp_code repr: {repr(otp_code)}")

        try:
            res_verify = self.session.post(
                f"{base_url}/cm/sms/smsOptCheck.do",
                data=verify_payload,
                timeout=10,
            )
            _debug_print(f"[DEBUG] smsOptCheck.do status={res_verify.status_code}")
            _debug_print(f"[DEBUG] smsOptCheck.do text (first 300):\n{res_verify.text[:300]}")

            try:
                verify_data = res_verify.json()
            except Exception as json_err:
                logger.error(f"smsOptCheck JSON parse failed: {json_err}")
                return False

            _debug_print(f"[DEBUG] smsOptCheck.do JSON: {verify_data}")
            if verify_data.get("errCode") == "F":
                logger.error(f"OTP verification failed: {verify_data.get('errMsg')}")
                return False

            is_post_step = verify_data.get("isPostStep", "")
            _debug_print(f"[DEBUG] isPostStep={is_post_step}")

            portal_jsession = self.session.cookies.get("JSESSIONID", "")
            login_url = f"{base_url}/cm/portal/login.do"
            if portal_jsession:
                login_url += f";jsessionid={portal_jsession}"

            auth_payload = {
                "certi": "",
                "USER_NM": self.user_id,
                "PASSWORD": self.password,
                "COMP_TYPE": self._comp_type,
                "eCatalogUrl": "",
                "eCatalogFlag": "",
                "linkGubun": "",
                "isPreStep": self._pre_step_token,
                "isPostStep": is_post_step,
            }
            res_auth = self.session.post(
                login_url,
                data=auth_payload,
                timeout=10,
                headers={"Referer": f"{base_url}/cm/portal/index.do"},
            )
            _debug_print(f"[DEBUG] portal login.do status={res_auth.status_code}")
            _debug_print(f"[DEBUG] portal login.do text (first 300):\n{res_auth.text[:300]}")

            bridge_form = extract_b2b_form_fields(res_auth.text)
            if bridge_form:
                bridge_form.setdefault("userName", self.user_id or "")
                bridge_form.setdefault("compCode", self.comp_code)
                bridge_form.setdefault("LINK_DIV", "")
                bridge_form.setdefault("LINK_URL", "")
                bridge_form.setdefault("FORM_YN", "N")
                self.b2b_bridge_form = bridge_form
                _debug_print(f"[DEBUG] bridge form keys: {sorted(self.b2b_bridge_form.keys())}")

            res_final = self.session.get(f"{base_url}/cm/portal/index.do", timeout=10)
            _debug_print(f"[DEBUG] final index.do status={res_final.status_code}")

            combined_text = res_auth.text + res_final.text
            _debug_print(f"[DEBUG] CM responses combined length: {len(combined_text)}")

            numeric_6 = re.findall(r"[^\d](\d{6})[^\d]", combined_text)
            if numeric_6:
                self.user_id_candidates = list(dict.fromkeys(numeric_6))
                _debug_print(f"[DEBUG] CM 6-digit candidates: {self.user_id_candidates}")

            self.internal_user_id = None

            self.session.headers.update({
                "If-Modified-Since": "Thu, 01 Jun 1970 00:00:00 GMT",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            })

            cookie_list = [(c.name, c.value) for c in self.session.cookies]
            _debug_print(f"[DEBUG] cookies after login: {cookie_list}")

            if any(c.name == "JSESSIONID" for c in self.session.cookies) and self.b2b_bridge_form.get("TOKEN"):
                logger.info("Portal login complete")
                self._logged_in = True
                self.touch_activity()
                return True

            logger.error("Portal login failed: missing session cookie or bridge token")
            return False

        except Exception as e:
            logger.error(f"login_step2 error: {e}")
            import traceback
            traceback.print_exc()
            return False

class ERPClient:
    """ERP API client."""

    def __init__(self, session: ERPSession):
        self.session = session
        self.last_error = ""

    def _build_service_headers(self, referer: str) -> dict[str, str]:
        return {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/xml, text/xml, */*",
            "Content-Type": "text/xml",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.6,en;q=0.4",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "If-Modified-Since": "Thu, 01 Jun 1970 00:00:00 GMT",
            "Expires": "-1",
            "Referer": referer,
        }

    def _get_cookie_variables(self) -> OrderedDict[str, str]:
        latest_cookie: dict[str, str] = {}
        for cookie in self.session.session.cookies:
            latest_cookie[cookie.name] = cookie.value

        cookie_vars: OrderedDict[str, str] = OrderedDict()
        cookie_vars["JSESSIONID"] = ""
        for name in ["L-VISITOR", "SCOUTER", "LENA-UID"]:
            value = latest_cookie.get(name, "")
            if value:
                cookie_vars[name] = value
        return cookie_vars

    def _build_b2b_cookie_header(self) -> str:
        latest_cookie: dict[str, str] = {}
        for cookie in self.session.session.cookies:
            latest_cookie[cookie.name] = cookie.value

        cookie_pairs: list[str] = []
        for name in ["L-VISITOR", "B2B_JSESSION", "SCOUTER", "LENA-UID", "JSESSIONID"]:
            value = latest_cookie.get(name, "")
            if value:
                cookie_pairs.append(f"{name}={value}")

        cookie_header = "; ".join(cookie_pairs)
        _debug_print(f"[DEBUG] B2B Cookie header: {cookie_header}")
        return cookie_header

    def _extract_user_context(self, parsed: dict[str, list[dict]]) -> None:
        login_rows = parsed.get("OUT_COME_LOGIN_INFO", [])
        if not login_rows:
            return

        login_info = login_rows[0]
        user_id = str(login_info.get("USER_ID", "")).strip()
        if user_id:
            self.session.internal_user_id = user_id
        channel_code = str(login_info.get("CHNL_CD", "")).strip()
        if channel_code:
            self.session.channel_code = channel_code
        comp_code = str(login_info.get("COMP_CD", "")).strip()
        if comp_code:
            self.session.comp_code = comp_code

        _debug_print(
            f"[DEBUG] B2B login context: userID={self.session.internal_user_id}, "
            f"CHNL_CD={self.session.channel_code}, COMP_CD={self.session.comp_code}"
        )

    def _bootstrap_b2b_login(self, token: str) -> bool:
        if not token:
            self.last_error = "B2B token not found"
            return False

        base_url = "https://newbest.lge.com"
        url = f"{base_url}/b2b/cm/nexacro/login.do"
        variables: OrderedDict[str, str] = OrderedDict()
        variables["JSESSIONID"] = ""
        variables.update({
            "baRq": "IN_PSET,RQSTDT",
            "baRs": "OUT_COME_LOGIN_INFO,OUT_COM_MSG,OUT_RESULT",
            "userID": "undefined",
            "menuCd": "",
        })
        datasets = {
            "IN_PSET": {
                "columns": ["USER_ID", "PASSWORD", "TOKEN", "PAD_FLAG", "LINK_DIV"],
                "rows": [["", "", token, "N", ""]],
            },
            "RQSTDT": {
                "columns": ["FAC_TYPE", "CACHE_TYPE"],
                "rows": [["MSG", "BROWSER-CACHE"]],
            },
        }
        headers = self._build_service_headers(f"{base_url}/b2b/NEWBEST/index.jsp")
        headers["Cookie"] = self._build_b2b_cookie_header()
        payload = SSVPayloadBuilder.build_payload(
            datasets,
            variables,
            null_for_empty=False,
        )

        res = self.session.session.post(
            url,
            data=payload.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
        _debug_print(f"[DEBUG] B2B nexacro login request cookie={res.request.headers.get('Cookie', '')}")
        _debug_print(f"[DEBUG] B2B nexacro login request body={payload[:500]}")
        _debug_print(f"[DEBUG] B2B nexacro login request body repr={payload[:500]!r}")
        _debug_print(f"[DEBUG] B2B nexacro login status={res.status_code}")
        _debug_print(
            f"[DEBUG] B2B nexacro login final url={res.url} "
            f"content-type={res.headers.get('Content-Type', '')} "
            f"history={[r.status_code for r in res.history]}"
        )
        _debug_print(f"[DEBUG] B2B nexacro login response (first 500):\n{res.text[:500]}")

        ssv_vars = NexacroSSVParser.parse_ssv_variables(res.text)
        error_code = ssv_vars.get("ErrorCode", "")
        error_msg = ssv_vars.get("ErrorMsg", "")
        parsed = NexacroSSVParser.parse_ssv_response(res.text)

        if error_code and error_code != "0":
            self.last_error = error_msg or f"B2B login failed (ErrorCode={error_code})"
            return False

        self._extract_user_context(parsed)
        return bool(self.session.internal_user_id)

    def _ensure_b2b_session(self, force_refresh: bool = False) -> bool:
        has_b2b = any(cookie.name == "B2B_JSESSION" for cookie in self.session.session.cookies)
        if has_b2b and self.session.internal_user_id and not force_refresh:
            return True

        bridge_form = dict(self.session.b2b_bridge_form)
        if not bridge_form:
            self.last_error = "B2B bridge form is missing. Please log in to ERP again."
            logger.error(self.last_error)
            return False

        bridge_form.setdefault("userName", self.session.user_id or "")
        bridge_form.setdefault("compCode", self.session.comp_code)
        bridge_form.setdefault("LINK_DIV", "")
        bridge_form.setdefault("LINK_URL", "")
        bridge_form.setdefault("FORM_YN", "N")

        base_url = "https://newbest.lge.com"
        portal_jsession = self.session.session.cookies.get("JSESSIONID", "")
        portal_referer = f"{base_url}/cm/portal/login.do"
        if portal_jsession:
            portal_referer += f";jsessionid={portal_jsession}"

        open_headers = {
            "Referer": portal_referer,
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
            "Accept-Language": "ko-KR",
            "Accept-Encoding": "gzip, deflate",
        }
        res_open = self.session.session.post(
            f"{base_url}/cm/portal/openMain.do",
            data=bridge_form,
            headers=open_headers,
            timeout=10,
        )
        _debug_print(f"[DEBUG] openMain.do status={res_open.status_code}")

        callback_form = extract_b2b_form_fields(res_open.text)
        if callback_form:
            _debug_print(f"[DEBUG] callback form keys: {sorted(callback_form.keys())}")

        index_payload: OrderedDict[str, str] = OrderedDict()
        for key in B2B_FORM_KEYS:
            if key in {"userName", "compCode"}:
                continue
            value = callback_form.get(key, bridge_form.get(key, ""))
            if value != "":
                index_payload[key] = value

        res_b2b = self.session.session.post(
            f"{base_url}/b2b/NEWBEST/index.jsp",
            data=index_payload,
            headers={
                "Referer": f"{base_url}/cm/portal/openMain.do",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-cache",
                "Accept-Language": "ko-KR",
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=10,
        )
        _debug_print(f"[DEBUG] B2B index.jsp status={res_b2b.status_code}")

        cookie_list = [(cookie.name, cookie.value[:20] + "...") for cookie in self.session.session.cookies]
        _debug_print(f"[DEBUG] cookies after B2B access: {cookie_list}")

        token = bridge_form.get("TOKEN") or callback_form.get("TOKEN", "")
        return self._bootstrap_b2b_login(token)

    def _call_b2b_service(
        self,
        service_name: str,
        datasets: dict,
        ba_rq: str,
        ba_rs: str,
        menu_cd: str = "XPMMM0404",
        allow_retry: bool = True,
    ) -> dict[str, list[dict]]:
        base_url = "https://newbest.lge.com"
        service_url = f"{base_url}/b2b/service/{service_name}/nexacro.ncd"

        for attempt in range(2 if allow_retry else 1):
            if not self._ensure_b2b_session(force_refresh=attempt > 0):
                return {}

            user_id = str(self.session.internal_user_id or "").strip()
            if not user_id:
                self.last_error = "ERP internal user ID is missing"
                logger.error(self.last_error)
                return {}

            variables = self._get_cookie_variables()
            variables.update({
                "baRq": ba_rq,
                "baRs": ba_rs,
                "userID": user_id,
                "menuCd": menu_cd,
            })
            headers = self._build_service_headers(f"{base_url}/b2b/NEWBEST/index.jsp")
            headers["Cookie"] = self._build_b2b_cookie_header()
            payload = SSVPayloadBuilder.build_payload(
                datasets,
                variables,
                null_for_empty=(service_name != "BRS_XPMMM_RetrieveEtcModelList"),
            )

            res = self.session.session.post(
                service_url,
                data=payload.encode("utf-8"),
                headers=headers,
                timeout=15,
            )
            _debug_print(f"[DEBUG] {service_name} request cookie={res.request.headers.get('Cookie', '')}")
            _debug_print(f"[DEBUG] {service_name} try#{attempt + 1} status={res.status_code}")
            _debug_print(f"[DEBUG] {service_name} response (first 500):\n{res.text[:500]}")

            ssv_vars = NexacroSSVParser.parse_ssv_variables(res.text)
            error_code = ssv_vars.get("ErrorCode", "")
            error_msg = ssv_vars.get("ErrorMsg", "")
            parsed = NexacroSSVParser.parse_ssv_response(res.text)
            _debug_print(f"[DEBUG] {service_name} parsed keys: {list(parsed.keys())}")

            if error_code and error_code != "0":
                self.last_error = f"{error_msg or 'ERP error'} (ErrorCode={error_code})"
                logger.error(f"{service_name} failed: {self.last_error}")
                if error_msg == "SessionNotFound" and attempt == 0 and allow_retry:
                    continue
                return {}

            if service_name == "BRS_XPMMM_RetrieveEtcModelList":
                self._extract_user_context(parsed)
            self.last_error = ""
            return parsed

        return {}

    @staticmethod
    def _to_int(value: str | int | float | None) -> int:
        try:
            return int(float(str(value or 0)))
        except (TypeError, ValueError):
            return 0

    def _sum_inventory_rows(self, inventory_rows: list[dict]) -> int:
        return sum(self._to_int(row.get("AVAILABLE_QTY")) for row in inventory_rows)

    def _prime_model_context(self, full_model: str) -> None:
        model_code_ds = {
            "IN_SEARCH": {
                "columns": ["MODEL_CODE"],
                "rows": [[full_model]],
            }
        }
        summary_ds = {
            "IN_SEARCH": {
                "columns": ["ITEM_ID", "MODEL_CODE", "CHNL_CD", "CUST_CD", "EXTERNAL_FLAG"],
                "rows": [["", full_model, self.session.channel_code, "", ""]],
            },
            "IN_AUTH_SET": {
                "columns": ["MENU_AUTH_LVL_CD", "DATA_APPRCH_AUTH_LVL_CD", "EXCEL_YN", "SEC_YN"],
                "rows": [["A", "1", "", ""]],
            },
        }

        self._call_b2b_service(
            "BRS_XPMMM_RetrieveModelChnlCheck",
            model_code_ds,
            "IN_SEARCH",
            "OUT_MODEL,OUT_RESULT,",
            allow_retry=False,
        )
        self._call_b2b_service(
            "BRS_XPMMM_RetrieveIncomLimit",
            model_code_ds,
            "IN_SEARCH",
            "OUT_MODEL,OUT_RESULT,",
            allow_retry=False,
        )
        self._call_b2b_service(
            "BRS_XPMMM_RetrieveLgeModelSummary",
            summary_ds,
            "IN_SEARCH,IN_AUTH_SET",
            "OUT_SUMMARY,OUT_RESULT",
            allow_retry=False,
        )

    def query_full_model(self, short_model: str) -> list[dict]:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return []

        self.last_error = ""
        datasets = {
            "IN_SEARCH": {
                "columns": [
                    "ITEM_CD",
                    "CAT_LVL1_CD",
                    "CAT_LVL2_CD",
                    "CAT_LVL3_CD",
                    "CAT_LVL4_CD",
                    "SEARCH_TYPE",
                    "BOM_ITEM_TYPE",
                    "ALL_STATUS_FLAG",
                ],
                "rows": [[short_model, "", "", "", "", "", "", ""]],
            }
        }
        parsed = self._call_b2b_service(
            "BRS_XPMMM_RetrieveEtcModelList",
            datasets,
            "IN_SEARCH",
            "OUT_LGEMODEL",
        )
        return parsed.get("OUT_LGEMODEL", [])

    def query_inventory(self, full_model: str) -> list[dict]:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return []

        self.last_error = ""
        self._prime_model_context(full_model)

        datasets = {
            "IN_SEARCH": {
                "columns": [
                    "ITEM_ID",
                    "ITEM_CD",
                    "DLS_ORG_CD",
                    "CAT_LVL1_CD",
                    "CAT_LVL2_CD",
                    "CAT_LVL3_CD",
                    "CAT_LVL4_CD",
                    "WH_ID",
                    "BOM_ITEM_TYPE",
                    "DELIV_DC_CD",
                    "HD_DELIV_DC_CD",
                    "BUILTIN_DC_CD",
                    "AIRCON_DC_CD",
                    "CHNL_CD",
                    "EXTERNAL_FLAG",
                ],
                "rows": [[
                    "",
                    full_model,
                    "",
                    "",
                    "",
                    "",
                    "",
                    self.session.inventory_wh_id,
                    "",
                    "",
                    "",
                    "",
                    "",
                    self.session.channel_code,
                    "N",
                ]],
            },
            "IN_AUTH_SET": {
                "columns": ["MENU_AUTH_LVL_CD", "DATA_APPRCH_AUTH_LVL_CD", "EXCEL_YN", "SEC_YN"],
                "rows": [["A", "1", "", ""]],
            },
        }
        parsed = self._call_b2b_service(
            "BRS_XPMMM_RetrieveLgeQty",
            datasets,
            "IN_SEARCH,IN_AUTH_SET",
            "OUT_LGEQTY,OUT_RESULT,OUT_DTLQTY",
        )
        return parsed.get("OUT_LGEQTY", [])

    def query_price_info(self, full_model: str) -> dict[str, int]:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return {}

        self.last_error = ""
        auth_parsed = self._call_b2b_service(
            "BRS_XHRCM_CheckPurPriceViewAuth",
            {},
            "",
            "OUT_PSET",
        )
        if self.last_error:
            return {}

        auth_rows = auth_parsed.get("OUT_PSET", [])
        if auth_rows:
            auth_flag = str(auth_rows[0].get("PUR_PRICE_VIEW_AUTH_YN", "")).strip().upper()
            if auth_flag and auth_flag != "Y":
                self.last_error = "공급가 조회 권한???�습?�다."
                return {}

        model_code_ds = {
            "IN_SEARCH": {
                "columns": ["MODEL_CODE"],
                "rows": [[full_model]],
            }
        }
        summary_ds = {
            "IN_SEARCH": {
                "columns": ["ITEM_ID", "MODEL_CODE", "CHNL_CD", "CUST_CD", "EXTERNAL_FLAG"],
                "rows": [["", full_model, self.session.channel_code, "", ""]],
            },
            "IN_AUTH_SET": {
                "columns": ["MENU_AUTH_LVL_CD", "DATA_APPRCH_AUTH_LVL_CD", "EXCEL_YN", "SEC_YN"],
                "rows": [["A", "1", "", ""]],
            },
        }

        self._call_b2b_service(
            "BRS_XPMMM_RetrieveModelChnlCheck",
            model_code_ds,
            "IN_SEARCH",
            "OUT_MODEL,OUT_RESULT,",
            allow_retry=False,
        )
        self._call_b2b_service(
            "BRS_XPMMM_RetrieveIncomLimit",
            model_code_ds,
            "IN_SEARCH",
            "OUT_MODEL,OUT_RESULT,",
            allow_retry=False,
        )
        parsed = self._call_b2b_service(
            "BRS_XPMMM_RetrieveLgeModelSummary",
            summary_ds,
            "IN_SEARCH,IN_AUTH_SET",
            "OUT_SUMMARY,OUT_RESULT",
            allow_retry=False,
        )

        rows = parsed.get("OUT_SUMMARY", [])
        if not rows:
            return {}

        row = rows[0]
        return {
            "supply_price": self._to_int(row.get("ORD_PRICE")),
            "shipment_price": self._to_int(row.get("SHMT_PRICE")),
            "order_price": self._to_int(row.get("ORD_PRICE")),
        }

    def query_production_plan_detail(self, full_model: str) -> ProductionPlanResult:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return ProductionPlanResult()

        self.last_error = ""
        header_ds = {
            "IN_SEARCH": {
                "columns": ["ITEM_CD"],
                "rows": [[full_model]],
            }
        }
        self._call_b2b_service(
            "BRS_XPMMM_RetrieveLgeProdPlanHeader",
            header_ds,
            "IN_SEARCH",
            "OUT_PLAN,OUT_RESULT",
        )

        detail_ds = {
            "IN_WS_PARAM": {
                "columns": ["PI_ITEM_CD"],
                "rows": [[full_model]],
            }
        }
        parsed = self._call_b2b_service(
            "BRS_XPMMM_RetrieveLgeProdPlanDtl",
            detail_ds,
            "IN_WS_PARAM",
            "OUT_WS_RESULT,OUT_RESULT_QTY,OUT_RESULT",
        )

        plan_row = None
        promised_row = None
        available_row = None
        for row in parsed.get("OUT_RESULT_QTY", []):
            gubun = str(row.get("GUBUN", "")).strip()
            gubun_nm = str(row.get("GUBUN_NM", "")).strip()
            if gubun == "Plan Qty" or gubun_nm == "?�산계획":
                plan_row = row
            elif gubun == "Consumed Qty" or gubun_nm == "?�기?�속???�산계획":
                promised_row = row
            elif gubun == "Available Qty" or gubun_nm == "?�기?�속 가???�산계획":
                available_row = row

        if not any((plan_row, promised_row, available_row)):
            return ProductionPlanResult()

        days: list[ProductionPlanDay] = []
        plan_total = 0
        promised_total = 0
        available_weekly_total = 0
        available_total = 0

        for i in range(0, 31):
            day_code = f"D{i:02d}"
            plan_qty = self._to_int(plan_row.get(day_code) if plan_row else 0)
            promised_qty = self._to_int(promised_row.get(day_code) if promised_row else 0)
            available_qty = self._to_int(available_row.get(day_code) if available_row else 0)

            plan_total += plan_qty
            promised_total += promised_qty
            available_total += available_qty
            if i <= 7:
                available_weekly_total += available_qty

            if plan_qty or promised_qty or available_qty:
                days.append(
                    ProductionPlanDay(
                        day_code=day_code,
                        plan_qty=plan_qty,
                        promised_qty=promised_qty,
                        available_qty=available_qty,
                    )
                )

        return ProductionPlanResult(
            plan_total=plan_total,
            promised_total=promised_total,
            available_weekly_total=available_weekly_total,
            available_total=available_total,
            days=tuple(days),
        )

    def select_best_inventory_model(
        self,
        query_model: str,
        models: list[dict],
    ) -> InventoryLookupResult | None:
        exact_models = filter_exact_prefix_models(query_model, models)
        if not exact_models:
            self.last_error = (
                f"?�력 모델 '{query_model}'�?'.' ??모델명이 ?�전???�치?�는 ERP 모델??찾�? 못했?�니??"
            )
            return None

        evaluations: list[InventoryLookupResult] = []
        for model in exact_models:
            item_cd = str(model.get("ITEM_CD", "")).strip()
            inventory_rows = self.query_inventory(item_cd)
            inventory_error = self.last_error.strip()
            inventory_total = self._sum_inventory_rows(inventory_rows)

            production_plan = self.query_production_plan_detail(item_cd)
            production_error = self.last_error.strip()

            score = inventory_total + production_plan.plan_total
            evaluations.append(
                InventoryLookupResult(
                    model=model,
                    inventory_rows=inventory_rows,
                    inventory_total=inventory_total,
                    inventory_error=inventory_error,
                    production_plan=production_plan,
                    production_error=production_error,
                    score=score,
                )
            )

        evaluations.sort(
            key=lambda item: (
                -item.score,
                -item.inventory_total,
                -item.production_plan.plan_total,
                str(item.model.get("ITEM_CD", "")).strip(),
            )
        )
        selected = evaluations[0]

        selection_note = ""
        if len(exact_models) > 1:
            selected_item_cd = str(selected.model.get("ITEM_CD", "")).strip()
            selection_note = (
                f"?�일 모델�?{len(exact_models)}�?�??�고+?�산계획 ?�계가 가??많�? "
                f"{selected_item_cd} 모델�??�시?�습?�다."
            )

        self.last_error = selected.production_error or selected.inventory_error
        return InventoryLookupResult(
            model=selected.model,
            inventory_rows=selected.inventory_rows,
            inventory_total=selected.inventory_total,
            inventory_error=selected.inventory_error,
            production_plan=selected.production_plan,
            production_error=selected.production_error,
            score=selected.score,
            selection_note=selection_note,
        )

    def query_production_plan(self, full_model: str) -> tuple[int, int]:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return (0, 0)

        self.last_error = ""
        header_ds = {
            "IN_SEARCH": {
                "columns": ["ITEM_CD"],
                "rows": [[full_model]],
            }
        }
        self._call_b2b_service(
            "BRS_XPMMM_RetrieveLgeProdPlanHeader",
            header_ds,
            "IN_SEARCH",
            "OUT_PLAN,OUT_RESULT",
        )

        detail_ds = {
            "IN_WS_PARAM": {
                "columns": ["PI_ITEM_CD"],
                "rows": [[full_model]],
            }
        }
        parsed = self._call_b2b_service(
            "BRS_XPMMM_RetrieveLgeProdPlanDtl",
            detail_ds,
            "IN_WS_PARAM",
            "OUT_WS_RESULT,OUT_RESULT_QTY,OUT_RESULT",
        )

        target_row = None
        for row in parsed.get("OUT_RESULT_QTY", []):
            if row.get("GUBUN") == "Available Qty" or row.get("GUBUN_NM") == "?�기?�속 가???�산계획":
                target_row = row
                break

        if not target_row:
            return (0, 0)

        weekly_total = sum(self._to_int(target_row.get(f"D{i:02d}")) for i in range(0, 8))
        monthly_total = sum(self._to_int(target_row.get(f"D{i:02d}")) for i in range(0, 31))
        return (weekly_total, monthly_total)

    def process_models(self, models: list[str], progress_callback=None) -> dict[str, dict]:
        results: dict[str, dict] = {}
        total = len(models)

        for idx, model in enumerate(models):
            model = (model or "").strip()
            if not model:
                continue

            full_models = self.query_full_model(model)
            best_match = self.select_best_inventory_model(model, full_models) if full_models else None
            if not best_match:
                results[model] = {
                    "inventory": 0,
                    "production_weekly": 0,
                    "production_total": 0,
                    "status": "model_not_found" if not self.last_error else "error",
                    "detail": self.last_error,
                }
            else:
                results[model] = {
                    "full_model": best_match.model.get("ITEM_CD", ""),
                    "inventory": best_match.inventory_total,
                    "production_weekly": best_match.production_plan.available_weekly_total,
                    "production_total": best_match.production_plan.available_total,
                    "status": "ok",
                    "detail": best_match.selection_note or best_match.production_error or best_match.inventory_error,
                }

            if progress_callback:
                progress_callback(idx + 1, total, model)

            time.sleep(0.05)

        return results

def write_erp_data_to_sheet(sheet, erp_results: dict):
    # TODO: excel_price_tables.py??로직�??�사?�게 결과 ?�이?��? ?��? ?�측??컬럼?�로 추�?
    pass
