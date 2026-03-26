"""
키움증권 REST API 클라이언트 (openapi.kiwoom.com)
- OAuth 토큰 관리 (au10001)
- 시세 조회 (현재가, 호가, 일봉/분봉)
- 주문 (매수/매도)
- 잔고 조회

Base URL:
  실전투자: https://api.kiwoom.com
  모의투자: https://mockapi.kiwoom.com
"""

import time
import json
import requests
from config import Config


class KiwoomAPI:
    def __init__(self):
        self.config = Config()
        self.base_url = self.config.BASE_URL
        self.access_token = None
        self.token_expires_at = 0

    # ─── 인증 (au10001) ─────────────────────────────────────

    def _get_token(self):
        """접근토큰 발급 (au10001)"""
        if self.access_token and time.time() < self.token_expires_at - 60:
            return self.access_token

        url = f"{self.base_url}/oauth2/token"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
        }
        body = {
            "grant_type": "client_credentials",
            "appkey": self.config.APP_KEY,
            "secretkey": self.config.SECRET_KEY,
        }
        resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        resp.raise_for_status()
        data = resp.json()

        self.access_token = data["token"]
        # 토큰 유효기간: 24시간
        self.token_expires_at = time.time() + 86400
        return self.access_token

    def _headers(self, api_id):
        """
        공통 요청 헤더
        :param api_id: API TR 코드 (예: ka10001, ka10080 등)
        """
        token = self._get_token()
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "appkey": self.config.APP_KEY,
            "secretkey": self.config.SECRET_KEY,
            "api-id": api_id,
        }

    def _get(self, path, api_id, params=None):
        """GET 요청"""
        url = f"{self.base_url}{path}"
        resp = requests.get(url, headers=self._headers(api_id), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path, api_id, body=None):
        """POST 요청"""
        url = f"{self.base_url}{path}"
        resp = requests.post(
            url, headers=self._headers(api_id),
            data=json.dumps(body) if body else None, timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    # ─── 시세 조회 ──────────────────────────────────────────

    def get_current_price(self, stock_code):
        """
        주식 현재가 조회
        :param stock_code: 종목코드 (예: "005930")
        :return: 현재가 정보 dict
        """
        params = {
            "stk_cd": stock_code,
        }
        data = self._get("/api/dostk/stkinfo", "ka10001", params)
        output = data.get("output", data)
        return {
            "stock_code": stock_code,
            "name": output.get("stk_nm", ""),
            "current_price": int(output.get("cur_prc", output.get("stck_prpr", 0))),
            "change": int(output.get("prdy_vrss", 0)),
            "change_rate": float(output.get("prdy_ctrt", 0)),
            "volume": int(output.get("acml_vol", 0)),
            "high": int(output.get("stck_hgpr", output.get("high_prc", 0))),
            "low": int(output.get("stck_lwpr", output.get("low_prc", 0))),
            "open": int(output.get("stck_oprc", output.get("open_prc", 0))),
        }

    def get_orderbook(self, stock_code):
        """
        호가 조회
        :param stock_code: 종목코드
        :return: 매수/매도 호가 리스트
        """
        params = {
            "stk_cd": stock_code,
        }
        data = self._get("/api/dostk/hogainfo", "ka10002", params)
        output = data.get("output", data)

        asks = []
        bids = []
        for i in range(1, 11):
            ask_price = output.get(f"askp{i}", output.get(f"sell_hoga{i}", 0))
            ask_vol = output.get(f"askp_rsqn{i}", output.get(f"sell_hoga_qty{i}", 0))
            bid_price = output.get(f"bidp{i}", output.get(f"buy_hoga{i}", 0))
            bid_vol = output.get(f"bidp_rsqn{i}", output.get(f"buy_hoga_qty{i}", 0))
            asks.append({"price": int(ask_price), "volume": int(ask_vol)})
            bids.append({"price": int(bid_price), "volume": int(bid_vol)})
        return {"asks": asks, "bids": bids}

    def get_daily_prices(self, stock_code, period="D", count=60):
        """
        일봉/분봉 데이터 조회 (ka10080: 분봉, ka10081: 일봉)
        :param stock_code: 종목코드
        :param period: D(일봉), 1(1분봉), 3(3분봉), 5(5분봉) 등
        :param count: 조회 개수
        :return: OHLCV 리스트
        """
        if period == "D":
            api_id = "ka10081"
            params = {
                "stk_cd": stock_code,
            }
        else:
            api_id = "ka10080"
            params = {
                "stk_cd": stock_code,
                "tic_scope": period,
            }

        data = self._get("/api/dostk/chart", api_id, params)
        items = data.get("output", data.get("data", []))
        if isinstance(items, dict):
            items = items.get("list", [])

        prices = []
        for item in items[:count]:
            prices.append({
                "date": item.get("date", item.get("stck_bsop_date", "")),
                "open": int(item.get("open_prc", item.get("stck_oprc", 0))),
                "high": int(item.get("high_prc", item.get("stck_hgpr", 0))),
                "low": int(item.get("low_prc", item.get("stck_lwpr", 0))),
                "close": int(item.get("close_prc", item.get("stck_clpr", 0))),
                "volume": int(item.get("acml_vol", item.get("vol", 0))),
            })
        return list(reversed(prices))

    # ─── 주문 ───────────────────────────────────────────────

    def buy(self, stock_code, qty, price=0, order_type="00"):
        """
        매수 주문
        :param stock_code: 종목코드
        :param qty: 수량
        :param price: 주문가격 (0이면 시장가)
        :param order_type: 00(지정가), 01(시장가)
        :return: 주문 결과
        """
        if price == 0:
            order_type = "01"

        body = {
            "account": self.config.ACCOUNT_NO,
            "stk_cd": stock_code,
            "order_type": order_type,
            "qty": str(qty),
            "price": str(price),
            "side": "buy",
        }
        return self._post("/api/dostk/order", "ka20001", body)

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

        body = {
            "account": self.config.ACCOUNT_NO,
            "stk_cd": stock_code,
            "order_type": order_type,
            "qty": str(qty),
            "price": str(price),
            "side": "sell",
        }
        return self._post("/api/dostk/order", "ka20001", body)

    # ─── 잔고/계좌 조회 ─────────────────────────────────────

    def get_balance(self):
        """
        계좌 잔고 조회
        :return: 보유종목 리스트 + 예수금 정보
        """
        params = {
            "account": self.config.ACCOUNT_NO,
        }
        data = self._get("/api/dostk/acntinfo", "ka30001", params)
        output = data.get("output", data)

        holdings = []
        stock_list = output.get("holdings", output.get("stock_list", []))
        for item in stock_list:
            qty = int(item.get("hldg_qty", item.get("qty", 0)))
            if qty > 0:
                holdings.append({
                    "stock_code": item.get("stk_cd", item.get("pdno", "")),
                    "name": item.get("stk_nm", item.get("prdt_name", "")),
                    "qty": qty,
                    "avg_price": int(float(item.get("avg_prc", item.get("pchs_avg_pric", 0)))),
                    "current_price": int(item.get("cur_prc", item.get("prpr", 0))),
                    "profit_loss": int(item.get("evlu_pfls_amt", item.get("pl_amt", 0))),
                    "profit_rate": float(item.get("evlu_pfls_rt", item.get("pl_rt", 0))),
                })

        return {
            "holdings": holdings,
            "total_eval": int(output.get("tot_evlu_amt", output.get("total_eval", 0))),
            "total_profit": int(output.get("evlu_pfls_smtl_amt", output.get("total_pl", 0))),
            "cash": int(output.get("dnca_tot_amt", output.get("deposit", 0))),
        }

    def get_order_history(self):
        """
        당일 주문 내역 조회
        :return: 주문 리스트
        """
        params = {
            "account": self.config.ACCOUNT_NO,
        }
        data = self._get("/api/dostk/orderinfo", "ka30002", params)
        orders = []
        items = data.get("output", data.get("data", []))
        if isinstance(items, dict):
            items = items.get("list", [])

        for item in items:
            orders.append({
                "order_no": item.get("odno", item.get("order_no", "")),
                "stock_code": item.get("stk_cd", item.get("pdno", "")),
                "name": item.get("stk_nm", item.get("prdt_name", "")),
                "side": "매수" if item.get("side", item.get("sll_buy_dvsn_cd", "")) in ("buy", "02") else "매도",
                "qty": int(item.get("qty", item.get("ord_qty", 0))),
                "price": int(item.get("price", item.get("ord_unpr", 0))),
                "executed_qty": int(item.get("executed_qty", item.get("tot_ccld_qty", 0))),
                "status": item.get("status", item.get("ord_dvsn_name", "")),
            })
        return orders
