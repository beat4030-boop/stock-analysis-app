"""
자동매매 봇
- 전략 기반 매매 실행
- 리스크 관리 (손절/익절)
- 매매 로그 기록
"""

import json
import logging
import os
from datetime import datetime

from kiwoom_api import KiwoomAPI
from strategies import AVAILABLE_STRATEGIES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

TRADE_LOG_FILE = "trade_history.json"


class TradingBot:
    def __init__(self):
        self.api = KiwoomAPI()
        self.is_running = False
        self.watchlist = []       # 감시 종목 리스트
        self.strategies = []      # 적용 전략 리스트
        self.trade_history = []   # 매매 이력

        # 리스크 관리 설정
        self.max_buy_amount = 1_000_000    # 1회 최대 매수 금액 (원)
        self.stop_loss_rate = -3.0         # 손절 기준 (%)
        self.take_profit_rate = 5.0        # 익절 기준 (%)
        self.max_holdings = 5              # 최대 보유 종목 수

        self._load_trade_history()

    # ─── 설정 ───────────────────────────────────────────────

    def set_watchlist(self, stock_codes):
        """감시 종목 설정"""
        self.watchlist = stock_codes
        logger.info(f"감시 종목 설정: {stock_codes}")

    def set_strategies(self, strategy_configs):
        """
        전략 설정
        :param strategy_configs: [{"name": "golden_cross", "params": {"short_period": 5}}]
        """
        self.strategies = []
        for cfg in strategy_configs:
            name = cfg["name"]
            params = cfg.get("params", {})
            if name in AVAILABLE_STRATEGIES:
                strategy = AVAILABLE_STRATEGIES[name](**params)
                self.strategies.append(strategy)
                logger.info(f"전략 추가: {strategy.name}")

    def set_risk_params(self, max_buy_amount=None, stop_loss=None, take_profit=None, max_holdings=None):
        """리스크 관리 파라미터 설정"""
        if max_buy_amount is not None:
            self.max_buy_amount = max_buy_amount
        if stop_loss is not None:
            self.stop_loss_rate = stop_loss
        if take_profit is not None:
            self.take_profit_rate = take_profit
        if max_holdings is not None:
            self.max_holdings = max_holdings
        logger.info(
            f"리스크 설정: 최대매수={self.max_buy_amount:,}원, "
            f"손절={self.stop_loss_rate}%, 익절={self.take_profit_rate}%, "
            f"최대보유={self.max_holdings}종목"
        )

    # ─── 매매 실행 ──────────────────────────────────────────

    def run_once(self):
        """1회 전략 평가 및 매매 실행"""
        if not self.strategies:
            logger.warning("설정된 전략 없음")
            return []

        results = []

        # 1. 보유 종목 손절/익절 체크
        self._check_stop_loss_take_profit(results)

        # 2. 감시 종목 전략 평가
        for stock_code in self.watchlist:
            try:
                result = self._evaluate_stock(stock_code)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"[{stock_code}] 평가 실패: {e}")
                results.append({
                    "stock_code": stock_code,
                    "action": "error",
                    "message": str(e),
                })

        return results

    def _evaluate_stock(self, stock_code):
        """개별 종목 전략 평가"""
        price_info = self.api.get_current_price(stock_code)
        current_price = price_info["current_price"]
        daily_prices = self.api.get_daily_prices(stock_code)

        buy_signals = 0
        sell_signals = 0
        reasons = []

        for strategy in self.strategies:
            signal, reason = strategy.evaluate(daily_prices, current_price)
            reasons.append(f"[{strategy.name}] {reason}")
            if signal == "buy":
                buy_signals += 1
            elif signal == "sell":
                sell_signals += 1

        # 과반수 전략이 동의하면 매매 실행
        threshold = len(self.strategies) / 2

        if buy_signals > threshold:
            return self._execute_buy(stock_code, current_price, reasons)
        elif sell_signals > threshold:
            return self._execute_sell(stock_code, current_price, reasons)

        return {
            "stock_code": stock_code,
            "name": price_info["name"],
            "action": "hold",
            "price": current_price,
            "reasons": reasons,
        }

    def _execute_buy(self, stock_code, current_price, reasons):
        """매수 실행"""
        balance = self.api.get_balance()

        # 최대 보유 종목 수 체크
        if len(balance["holdings"]) >= self.max_holdings:
            msg = f"최대 보유 종목 수 초과 ({self.max_holdings})"
            logger.info(f"[{stock_code}] 매수 스킵: {msg}")
            return {"stock_code": stock_code, "action": "skip", "message": msg}

        # 이미 보유 중인지 체크
        for h in balance["holdings"]:
            if h["stock_code"] == stock_code:
                msg = "이미 보유 중"
                logger.info(f"[{stock_code}] 매수 스킵: {msg}")
                return {"stock_code": stock_code, "action": "skip", "message": msg}

        # 매수 수량 계산
        qty = int(self.max_buy_amount / current_price)
        if qty <= 0:
            msg = "매수 가능 수량 없음"
            return {"stock_code": stock_code, "action": "skip", "message": msg}

        # 예수금 체크
        required = qty * current_price
        if required > balance["cash"]:
            qty = int(balance["cash"] / current_price)
            if qty <= 0:
                msg = "예수금 부족"
                return {"stock_code": stock_code, "action": "skip", "message": msg}

        # 시장가 매수
        logger.info(f"[{stock_code}] 매수 주문: {qty}주 × {current_price:,}원")
        result = self.api.buy(stock_code, qty, price=0)

        trade = {
            "timestamp": datetime.now().isoformat(),
            "stock_code": stock_code,
            "action": "buy",
            "qty": qty,
            "price": current_price,
            "amount": qty * current_price,
            "reasons": reasons,
            "result": result,
        }
        self._record_trade(trade)

        return trade

    def _execute_sell(self, stock_code, current_price, reasons):
        """매도 실행"""
        balance = self.api.get_balance()
        holding = None
        for h in balance["holdings"]:
            if h["stock_code"] == stock_code:
                holding = h
                break

        if not holding:
            return {"stock_code": stock_code, "action": "skip", "message": "보유 종목 아님"}

        qty = holding["qty"]
        logger.info(f"[{stock_code}] 매도 주문: {qty}주 × {current_price:,}원")
        result = self.api.sell(stock_code, qty, price=0)

        trade = {
            "timestamp": datetime.now().isoformat(),
            "stock_code": stock_code,
            "action": "sell",
            "qty": qty,
            "price": current_price,
            "amount": qty * current_price,
            "reasons": reasons,
            "result": result,
        }
        self._record_trade(trade)

        return trade

    def _check_stop_loss_take_profit(self, results):
        """보유 종목 손절/익절 체크"""
        try:
            balance = self.api.get_balance()
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return

        for holding in balance["holdings"]:
            profit_rate = holding["profit_rate"]
            stock_code = holding["stock_code"]

            if profit_rate <= self.stop_loss_rate:
                logger.warning(
                    f"[{stock_code}] 손절 발동: 수익률 {profit_rate:.1f}% <= {self.stop_loss_rate}%"
                )
                result = self._execute_sell(
                    stock_code, holding["current_price"],
                    [f"손절: 수익률 {profit_rate:.1f}%"]
                )
                results.append(result)

            elif profit_rate >= self.take_profit_rate:
                logger.info(
                    f"[{stock_code}] 익절 발동: 수익률 {profit_rate:.1f}% >= {self.take_profit_rate}%"
                )
                result = self._execute_sell(
                    stock_code, holding["current_price"],
                    [f"익절: 수익률 {profit_rate:.1f}%"]
                )
                results.append(result)

    # ─── 이력 관리 ──────────────────────────────────────────

    def _record_trade(self, trade):
        """매매 이력 저장"""
        self.trade_history.append(trade)
        self._save_trade_history()

    def _save_trade_history(self):
        """매매 이력 파일 저장"""
        try:
            with open(TRADE_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"이력 저장 실패: {e}")

    def _load_trade_history(self):
        """매매 이력 파일 로드"""
        if os.path.exists(TRADE_LOG_FILE):
            try:
                with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
                    self.trade_history = json.load(f)
            except Exception:
                self.trade_history = []

    def get_status(self):
        """봇 상태 반환"""
        return {
            "is_running": self.is_running,
            "watchlist": self.watchlist,
            "strategies": [s.name for s in self.strategies],
            "risk_params": {
                "max_buy_amount": self.max_buy_amount,
                "stop_loss_rate": self.stop_loss_rate,
                "take_profit_rate": self.take_profit_rate,
                "max_holdings": self.max_holdings,
            },
            "trade_count": len(self.trade_history),
            "recent_trades": self.trade_history[-10:],
        }
