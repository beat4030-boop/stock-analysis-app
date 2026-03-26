"""
Flask 서버 - 자동매매 API + 대시보드 백엔드
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from kiwoom_api import KiwoomAPI
from trading_bot import TradingBot
from strategies import AVAILABLE_STRATEGIES

app = Flask(__name__)
CORS(app)

config = Config()
api = KiwoomAPI()
bot = TradingBot()
scheduler = BackgroundScheduler()


# ─── 시세 조회 API ──────────────────────────────────────────

@app.route("/api/price/<stock_code>")
def get_price(stock_code):
    """현재가 조회"""
    try:
        data = api.get_current_price(stock_code)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/orderbook/<stock_code>")
def get_orderbook(stock_code):
    """호가 조회"""
    try:
        data = api.get_orderbook(stock_code)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/daily/<stock_code>")
def get_daily(stock_code):
    """일봉 데이터 조회"""
    try:
        period = request.args.get("period", "D")
        count = int(request.args.get("count", 60))
        data = api.get_daily_prices(stock_code, period, count)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 계좌 API ───────────────────────────────────────────────

@app.route("/api/balance")
def get_balance():
    """계좌 잔고 조회"""
    try:
        data = api.get_balance()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/orders")
def get_orders():
    """주문 내역 조회"""
    try:
        data = api.get_order_history()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 수동 주문 API ──────────────────────────────────────────

@app.route("/api/order/buy", methods=["POST"])
def order_buy():
    """매수 주문"""
    try:
        body = request.json
        stock_code = body["stock_code"]
        qty = int(body["qty"])
        price = int(body.get("price", 0))
        result = api.buy(stock_code, qty, price)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/order/sell", methods=["POST"])
def order_sell():
    """매도 주문"""
    try:
        body = request.json
        stock_code = body["stock_code"]
        qty = int(body["qty"])
        price = int(body.get("price", 0))
        result = api.sell(stock_code, qty, price)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 자동매매 봇 API ────────────────────────────────────────

@app.route("/api/bot/status")
def bot_status():
    """봇 상태 조회"""
    return jsonify(bot.get_status())


@app.route("/api/bot/configure", methods=["POST"])
def bot_configure():
    """봇 설정"""
    try:
        body = request.json

        if "watchlist" in body:
            bot.set_watchlist(body["watchlist"])

        if "strategies" in body:
            bot.set_strategies(body["strategies"])

        if "risk_params" in body:
            rp = body["risk_params"]
            bot.set_risk_params(
                max_buy_amount=rp.get("max_buy_amount"),
                stop_loss=rp.get("stop_loss_rate"),
                take_profit=rp.get("take_profit_rate"),
                max_holdings=rp.get("max_holdings"),
            )

        return jsonify({"status": "ok", "bot": bot.get_status()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/start", methods=["POST"])
def bot_start():
    """자동매매 시작"""
    try:
        interval = request.json.get("interval_seconds", 60)

        if bot.is_running:
            return jsonify({"error": "이미 실행 중"}), 400

        bot.is_running = True

        if scheduler.get_job("auto_trade"):
            scheduler.remove_job("auto_trade")

        scheduler.add_job(
            bot.run_once,
            "interval",
            seconds=interval,
            id="auto_trade",
            replace_existing=True,
        )
        if not scheduler.running:
            scheduler.start()

        return jsonify({"status": "started", "interval": interval})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/stop", methods=["POST"])
def bot_stop():
    """자동매매 중지"""
    try:
        bot.is_running = False
        if scheduler.get_job("auto_trade"):
            scheduler.remove_job("auto_trade")
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/run-once", methods=["POST"])
def bot_run_once():
    """1회 수동 실행"""
    try:
        results = bot.run_once()
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/history")
def bot_history():
    """매매 이력 조회"""
    return jsonify(bot.trade_history)


@app.route("/api/strategies")
def list_strategies():
    """사용 가능한 전략 목록"""
    result = {}
    for key, cls in AVAILABLE_STRATEGIES.items():
        s = cls()
        result[key] = {"name": s.name, "key": key}
    return jsonify(result)


# ─── 서버 실행 ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  키움증권 자동매매 서버")
    print(f"  모의투자: {config.IS_PAPER_TRADING}")
    print(f"  계좌번호: {config.ACCOUNT_NO}")
    print("=" * 50)
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
