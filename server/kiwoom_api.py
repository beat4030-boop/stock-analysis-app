"""
키움증권 REST API 클라이언트
- OAuth 토큰 관리
- 시세 조회 (현재가, 호가, 일봉/분봉)
- 주문 (매수/매도/정정/취소)
- 잔고 조회
"""

import time
import requests
from config import Config


class KiwoomAPI:
    def __init__(self):
        self.config = Config()
        self.base_url = self.config.BASE_URL
        self.access_token = None
        self.token_expires_at = 0

    # ─── 인증 ───────────────────────────────────────────────

    def _get_token(self):
        """OAuth 접근 토큰 발급"""
        if self.access_token and time.time() < self.token_expires_at - 60:
            return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.config.APP_KEY,
            "appsecret": self.config.APP_SECRET,
        }
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        self.access_token = data["access_token"]
        self.token_expires_at = time.time() + data.get("expires_in", 86400)
        return self.access_token

    def _headers(self, tr_id):
        """공통 요청 헤더"""
        token = self._get_token()
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.config.APP_KEY,
            "appsecret": self.config.APP_SECRET,
            "tr_id": tr_id,
        }

    def _get(self, path, tr_id, params=None):
        """GET 요청 헬퍼"""
        url = f"{self.base_url}{path}"
        resp = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path, tr_id, body=None):
        """POST 요청 헬퍼"""
        url = f"{self.base_url}{path}"
        resp = requests.post(url, headers=self._headers(tr_id), json=body, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ─── 시세 조회 ──────────────────────────────────────────

    def get_current_price(self, stock_code):
        """
        주식 현재가 조회
        :param stock_code: 종목코드 (예: "005930")
        :return: 현재가 정보 dict
        """
        tr_id = "FHKST01010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 주식
            "FID_INPUT_ISCD": stock_code,
        }
        data = self._get("/uapi/domestic-stock/v1/quotations/inquire-price", tr_id, params)
        output = data.get("output", {})
        return {
            "stock_code": stock_code,
            "name": output.get("hts_kor_isnm", ""),
            "current_price": int(output.get("stck_prpr", 0)),
            "change": int(output.get("prdy_vrss", 0)),
            "change_rate": float(output.get("prdy_ctrt", 0)),
            "volume": int(output.get("acml_vol", 0)),
            "high": int(output.get("stck_hgpr", 0)),
            "low": int(output.get("stck_lwpr", 0)),
            "open": int(output.get("stck_oprc", 0)),
        }

    def get_orderbook(self, stock_code):
        """
        호가 조회
        :param stock_code: 종목코드
        :return: 매수/매도 호가 리스트
        """
        tr_id = "FHKST01010200"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }
        data = self._get("/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn", tr_id, params)
        output = data.get("output1", {})

        asks = []
        bids = []
        for i in range(1, 11):
            asks.append({
                "price": int(output.get(f"askp{i}", 0)),
                "volume": int(output.get(f"askp_rsqn{i}", 0)),
            })
            bids.append({
                "price": int(output.get(f"bidp{i}", 0)),
                "volume": int(output.get(f"bidp_rsqn{i}", 0)),
            })
        return {"asks": asks, "bids": bids}

    def get_daily_prices(self, stock_code, period="D", count=60):
        """
        일봉/주봉/월봉 데이터 조회
        :param stock_code: 종목코드
        :param period: D(일), W(주), M(월)
        :param count: 조회 개수
        :return: OHLCV 리스트
        """
        tr_id = "FHKST01010400"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0",  # 수정주가 반영
        }
        data = self._get("/uapi/domestic-stock/v1/quotations/inquire-daily-price", tr_id, params)
        prices = []
        for item in data.get("output", [])[:count]:
            prices.append({
                "date": item.get("stck_bsop_date", ""),
                "open": int(item.get("stck_oprc", 0)),
                "high": int(item.get("stck_hgpr", 0)),
                "low": int(item.get("stck_lwpr", 0)),
                "close": int(item.get("stck_clpr", 0)),
                "volume": int(item.get("acml_vol", 0)),
            })
        return list(reversed(prices))

    # ─── 주문 ───────────────────────────────────────────────

    def _order_tr_id(self, side):
        """주문 TR_ID (모의투자/실전 분기)"""
        if self.config.IS_PAPER_TRADING:
            return "VTTC0802U" if side == "buy" else "VTTC0801U"
        return "TTTC0802U" if side == "buy" else "TTTC0801U"

    def buy(self, stock_code, qty, price=0, order_type="00"):
        """
        매수 주문
        :param stock_code: 종목코드
        :param qty: 수량
        :param price: 주문가격 (0이면 시장가)
        :param order_type: 00(지정가), 01(시장가), 02(조건부지정가)
        :return: 주문 결과
        """
        if price == 0:
            order_type = "01"

        tr_id = self._order_tr_id("buy")
        body = {
            "CANO": self.config.cano,
            "ACNT_PRDT_CD": self.config.acnt_prdt_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }
        return self._post("/uapi/domestic-stock/v1/trading/order-cash", tr_id, body)

    def sell(self, stock_code, qty, price=0, order_type="00"):
        """
        매도 주문
        :param stock_code: 종목코드
        :param qty: 수량
        :param price: 주문가격 (0이면 시장가)
        :param order_type: 00(지정가), 01(시장가)
        :return: 주문 결과
        """
        if price == 0:
            order_type = "01"

        tr_id = self._order_tr_id("sell")
        body = {
            "CANO": self.config.cano,
            "ACNT_PRDT_CD": self.config.acnt_prdt_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }
        return self._post("/uapi/domestic-stock/v1/trading/order-cash", tr_id, body)

    # ─── 잔고/계좌 조회 ─────────────────────────────────────

    def get_balance(self):
        """
        계좌 잔고 조회
        :return: 보유종목 리스트 + 예수금 정보
        """
        tr_id = "VTTC8434R" if self.config.IS_PAPER_TRADING else "TTTC8434R"
        params = {
            "CANO": self.config.cano,
            "ACNT_PRDT_CD": self.config.acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        data = self._get("/uapi/domestic-stock/v1/trading/inquire-balance", tr_id, params)

        holdings = []
        for item in data.get("output1", []):
            if int(item.get("hldg_qty", 0)) > 0:
                holdings.append({
                    "stock_code": item.get("pdno", ""),
                    "name": item.get("prdt_name", ""),
                    "qty": int(item.get("hldg_qty", 0)),
                    "avg_price": int(float(item.get("pchs_avg_pric", 0))),
                    "current_price": int(item.get("prpr", 0)),
                    "profit_loss": int(item.get("evlu_pfls_amt", 0)),
                    "profit_rate": float(item.get("evlu_pfls_rt", 0)),
                })

        account_info = data.get("output2", [{}])
        if isinstance(account_info, list) and account_info:
            account_info = account_info[0]

        return {
            "holdings": holdings,
            "total_eval": int(account_info.get("tot_evlu_amt", 0)),
            "total_profit": int(account_info.get("evlu_pfls_smtl_amt", 0)),
            "cash": int(account_info.get("dnca_tot_amt", 0)),
        }

    def get_order_history(self):
        """
        당일 주문 내역 조회
        :return: 주문 리스트
        """
        tr_id = "VTTC8001R" if self.config.IS_PAPER_TRADING else "TTTC8001R"
        params = {
            "CANO": self.config.cano,
            "ACNT_PRDT_CD": self.config.acnt_prdt_cd,
            "INQR_STRT_DT": "",
            "INQR_END_DT": "",
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "PDNO": "",
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        data = self._get("/uapi/domestic-stock/v1/trading/inquire-daily-ccld", tr_id, params)
        orders = []
        for item in data.get("output1", []):
            orders.append({
                "order_no": item.get("odno", ""),
                "stock_code": item.get("pdno", ""),
                "name": item.get("prdt_name", ""),
                "side": "매수" if item.get("sll_buy_dvsn_cd") == "02" else "매도",
                "qty": int(item.get("ord_qty", 0)),
                "price": int(item.get("ord_unpr", 0)),
                "executed_qty": int(item.get("tot_ccld_qty", 0)),
                "status": item.get("ord_dvsn_name", ""),
            })
        return orders
