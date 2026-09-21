
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
        _debug_print(f"[DEBUG] B2B nexacro login status={res.status_code}")
        
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
        }
        res_open = self.session.session.post(
            f"{base_url}/cm/portal/openMain.do",
            data=bridge_form,
            headers=open_headers,
            timeout=10,
        )

        callback_form = extract_b2b_form_fields(res_open.text)
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
            },
            timeout=10,
        )

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

            ssv_vars = NexacroSSVParser.parse_ssv_variables(res.text)
            error_code = ssv_vars.get("ErrorCode", "")
            error_msg = ssv_vars.get("ErrorMsg", "")
            parsed = NexacroSSVParser.parse_ssv_response(res.text)

            if error_code and error_code != "0":
                self.last_error = f"{error_msg or 'ERP error'} (ErrorCode={error_code})"
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

        self._call_b2b_service("BRS_XPMMM_RetrieveModelChnlCheck", model_code_ds, "IN_SEARCH", "OUT_MODEL,OUT_RESULT,", allow_retry=False)
        self._call_b2b_service("BRS_XPMMM_RetrieveIncomLimit", model_code_ds, "IN_SEARCH", "OUT_MODEL,OUT_RESULT,", allow_retry=False)
        self._call_b2b_service("BRS_XPMMM_RetrieveLgeModelSummary", summary_ds, "IN_SEARCH,IN_AUTH_SET", "OUT_SUMMARY,OUT_RESULT", allow_retry=False)

    def query_full_model(self, short_model: str) -> list[dict]:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return []

        self.last_error = ""
        datasets = {
            "IN_SEARCH": {
                "columns": ["ITEM_CD", "CAT_LVL1_CD", "CAT_LVL2_CD", "CAT_LVL3_CD", "CAT_LVL4_CD", "SEARCH_TYPE", "BOM_ITEM_TYPE", "ALL_STATUS_FLAG"],
                "rows": [[short_model, "", "", "", "", "", "", ""]],
            }
        }
        parsed = self._call_b2b_service("BRS_XPMMM_RetrieveEtcModelList", datasets, "IN_SEARCH", "OUT_LGEMODEL")
        return parsed.get("OUT_LGEMODEL", [])

    def query_inventory(self, full_model: str) -> list[dict]:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return []

        self.last_error = ""
        self._prime_model_context(full_model)

        datasets = {
            "IN_SEARCH": {
                "columns": ["ITEM_ID", "ITEM_CD", "DLS_ORG_CD", "CAT_LVL1_CD", "CAT_LVL2_CD", "CAT_LVL3_CD", "CAT_LVL4_CD", "WH_ID", "BOM_ITEM_TYPE", "DELIV_DC_CD", "HD_DELIV_DC_CD", "BUILTIN_DC_CD", "AIRCON_DC_CD", "CHNL_CD", "EXTERNAL_FLAG"],
                "rows": [["", full_model, "", "", "", "", "", self.session.inventory_wh_id, "", "", "", "", "", self.session.channel_code, "N"]],
            },
            "IN_AUTH_SET": {
                "columns": ["MENU_AUTH_LVL_CD", "DATA_APPRCH_AUTH_LVL_CD", "EXCEL_YN", "SEC_YN"],
                "rows": [["A", "1", "", ""]],
            },
        }
        parsed = self._call_b2b_service("BRS_XPMMM_RetrieveLgeQty", datasets, "IN_SEARCH,IN_AUTH_SET", "OUT_LGEQTY,OUT_RESULT,OUT_DTLQTY")
        return parsed.get("OUT_LGEQTY", [])

    def query_price_info(self, full_model: str) -> dict[str, int]:
        if not self.session.user_id:
            logger.error("ERP session is not logged in")
            return {}

        self.last_error = ""
        auth_parsed = self._call_b2b_service("BRS_XHRCM_CheckPurPriceViewAuth", {}, "", "OUT_PSET")
        if self.last_error: return {}

        auth_rows = auth_parsed.get("OUT_PSET", [])
        if auth_rows:
            auth_flag = str(auth_rows[0].get("PUR_PRICE_VIEW_AUTH_YN", "")).strip().upper()
            if auth_flag and auth_flag != "Y":
                self.last_error = "공급가 조회 권한이 없습니다."
                return {}

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
        parsed = self._call_b2b_service("BRS_XPMMM_RetrieveLgeModelSummary", summary_ds, "IN_SEARCH,IN_AUTH_SET", "OUT_SUMMARY,OUT_RESULT", allow_retry=False)
        rows = parsed.get("OUT_SUMMARY", [])
        if not rows: return {}

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
        detail_ds = { "IN_WS_PARAM": { "columns": ["PI_ITEM_CD"], "rows": [[full_model]] } }
        parsed = self._call_b2b_service("BRS_XPMMM_RetrieveLgeProdPlanDtl", detail_ds, "IN_WS_PARAM", "OUT_WS_RESULT,OUT_RESULT_QTY,OUT_RESULT")

        plan_row = promised_row = available_row = None
        for row in parsed.get("OUT_RESULT_QTY", []):
            gubun = str(row.get("GUBUN", "")).strip()
            gubun_nm = str(row.get("GUBUN_NM", "")).strip()
            if gubun == "Plan Qty" or gubun_nm == "생산계획": plan_row = row
            elif gubun == "Consumed Qty" or gubun_nm == "납기약속된 생산계획": promised_row = row
            elif gubun == "Available Qty" or gubun_nm == "납기약속 가능 생산계획": available_row = row

        if not any((plan_row, promised_row, available_row)): return ProductionPlanResult()

        days: list[ProductionPlanDay] = []
        plan_total = promised_total = available_weekly_total = available_total = 0

        for i in range(0, 31):
            day_code = f"D{i:02d}"
            plan_qty = self._to_int(plan_row.get(day_code) if plan_row else 0)
            promised_qty = self._to_int(promised_row.get(day_code) if promised_row else 0)
            available_qty = self._to_int(available_row.get(day_code) if available_row else 0)

            plan_total += plan_qty
            promised_total += promised_qty
            available_total += available_qty
            if i <= 7: available_weekly_total += available_qty

            if plan_qty or promised_qty or available_qty:
                days.append(ProductionPlanDay(day_code=day_code, plan_qty=plan_qty, promised_qty=promised_qty, available_qty=available_qty))

        return ProductionPlanResult(plan_total=plan_total, promised_total=promised_total, available_weekly_total=available_weekly_total, available_total=available_total, days=tuple(days))

    def select_best_inventory_model(self, query_model: str, models: list[dict]) -> InventoryLookupResult | None:
        exact_models = filter_exact_prefix_models(query_model, models)
        if not exact_models:
            self.last_error = f"입력 모델 '{query_model}'의 '.' 앞 모델명이 완전히 일치하는 ERP 모델을 찾지 못했습니다."
            return None

        evaluations: list[InventoryLookupResult] = []
        for model in exact_models:
            item_cd = str(model.get("ITEM_CD", "")).strip()
            inventory_rows = self.query_inventory(item_cd)
            inventory_total = self._sum_inventory_rows(inventory_rows)
            production_plan = self.query_production_plan_detail(item_cd)
            evaluations.append(InventoryLookupResult(model=model, inventory_rows=inventory_rows, inventory_total=inventory_total, inventory_error=self.last_error, production_plan=production_plan, production_error=self.last_error, score=inventory_total + production_plan.plan_total))

        evaluations.sort(key=lambda item: (-item.score, -item.inventory_total, -item.production_plan.plan_total, str(item.model.get("ITEM_CD", "")).strip()))
        selected = evaluations[0]
        selection_note = f"단일 모델명 {len(exact_models)}개 대상 재고+생산계획 합계가 가장 많은 {selected.model.get('ITEM_CD')} 모델을 표시했습니다." if len(exact_models) > 1 else ""
        return InventoryLookupResult(model=selected.model, inventory_rows=selected.inventory_rows, inventory_total=selected.inventory_total, inventory_error=selected.inventory_error, production_plan=selected.production_plan, production_error=selected.production_error, score=selected.score, selection_note=selection_note)

    def process_models(self, models: list[str], progress_callback=None) -> dict[str, dict]:
        results = {}
        total = len(models)
        for idx, model in enumerate(models):
            model = (model or "").strip()
            if not model: continue
            full_models = self.query_full_model(model)
            best_match = self.select_best_inventory_model(model, full_models) if full_models else None
            if not best_match:
                results[model] = { "inventory": 0, "production_weekly": 0, "production_total": 0, "status": "model_not_found", "detail": self.last_error }
            else:
                results[model] = { "full_model": best_match.model.get("ITEM_CD", ""), "inventory": best_match.inventory_total, "production_weekly": best_match.production_plan.available_weekly_total, "production_total": best_match.production_plan.available_total, "status": "ok", "detail": best_match.selection_note or best_match.production_error or best_match.inventory_error }
            if progress_callback: progress_callback(idx + 1, total, model)
            time.sleep(0.05)
        return results

def write_erp_data_to_sheet(sheet, erp_results: dict):
    pass
