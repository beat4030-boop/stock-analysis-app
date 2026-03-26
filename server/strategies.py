"""
자동매매 전략 모듈
- 이동평균 골든크로스/데드크로스
- RSI 과매수/과매도
- 볼린저 밴드 전략
- 변동성 돌파 전략
"""


def calc_ma(prices, period):
    """이동평균 계산"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def calc_rsi(prices, period=14):
    """RSI 계산"""
    if len(prices) < period + 1:
        return None

    gains = []
    losses = []
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_bollinger(prices, period=20, num_std=2):
    """볼린저 밴드 계산"""
    if len(prices) < period:
        return None, None, None

    window = prices[-period:]
    mid = sum(window) / period
    variance = sum((p - mid) ** 2 for p in window) / period
    std = variance ** 0.5

    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


class Strategy:
    """전략 기본 클래스"""

    def __init__(self, name):
        self.name = name

    def evaluate(self, prices, current_price):
        """
        전략 평가
        :return: ("buy", reason), ("sell", reason), 또는 ("hold", reason)
        """
        raise NotImplementedError


class GoldenCrossStrategy(Strategy):
    """이동평균 골든크로스/데드크로스 전략"""

    def __init__(self, short_period=5, long_period=20):
        super().__init__(f"이동평균({short_period}/{long_period})")
        self.short_period = short_period
        self.long_period = long_period

    def evaluate(self, prices, current_price):
        if len(prices) < self.long_period + 1:
            return "hold", "데이터 부족"

        closes = [p["close"] for p in prices]

        ma_short = calc_ma(closes, self.short_period)
        ma_long = calc_ma(closes, self.long_period)
        prev_ma_short = calc_ma(closes[:-1], self.short_period)
        prev_ma_long = calc_ma(closes[:-1], self.long_period)

        if prev_ma_short <= prev_ma_long and ma_short > ma_long:
            return "buy", f"골든크로스 발생 (MA{self.short_period}={ma_short:.0f} > MA{self.long_period}={ma_long:.0f})"

        if prev_ma_short >= prev_ma_long and ma_short < ma_long:
            return "sell", f"데드크로스 발생 (MA{self.short_period}={ma_short:.0f} < MA{self.long_period}={ma_long:.0f})"

        if ma_short > ma_long:
            return "hold", f"상승 추세 유지 (MA{self.short_period}={ma_short:.0f} > MA{self.long_period}={ma_long:.0f})"
        return "hold", f"하락 추세 유지 (MA{self.short_period}={ma_short:.0f} < MA{self.long_period}={ma_long:.0f})"


class RSIStrategy(Strategy):
    """RSI 과매수/과매도 전략"""

    def __init__(self, period=14, oversold=30, overbought=70):
        super().__init__(f"RSI({period})")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def evaluate(self, prices, current_price):
        closes = [p["close"] for p in prices]
        rsi = calc_rsi(closes, self.period)

        if rsi is None:
            return "hold", "데이터 부족"

        if rsi <= self.oversold:
            return "buy", f"RSI 과매도 ({rsi:.1f} <= {self.oversold})"

        if rsi >= self.overbought:
            return "sell", f"RSI 과매수 ({rsi:.1f} >= {self.overbought})"

        return "hold", f"RSI 중립 ({rsi:.1f})"


class BollingerStrategy(Strategy):
    """볼린저 밴드 전략"""

    def __init__(self, period=20, num_std=2):
        super().__init__(f"볼린저밴드({period},{num_std})")
        self.period = period
        self.num_std = num_std

    def evaluate(self, prices, current_price):
        closes = [p["close"] for p in prices]
        upper, mid, lower = calc_bollinger(closes, self.period, self.num_std)

        if upper is None:
            return "hold", "데이터 부족"

        if current_price <= lower:
            return "buy", f"하단 밴드 터치 (현재가={current_price:,} <= 하단={lower:,.0f})"

        if current_price >= upper:
            return "sell", f"상단 밴드 터치 (현재가={current_price:,} >= 상단={upper:,.0f})"

        return "hold", f"밴드 내 (하단={lower:,.0f} / 현재={current_price:,} / 상단={upper:,.0f})"


class VolatilityBreakoutStrategy(Strategy):
    """변동성 돌파 전략 (래리 윌리엄스)"""

    def __init__(self, k=0.5):
        super().__init__(f"변동성돌파(K={k})")
        self.k = k

    def evaluate(self, prices, current_price):
        if len(prices) < 2:
            return "hold", "데이터 부족"

        yesterday = prices[-1]
        prev_range = yesterday["high"] - yesterday["low"]
        target_price = yesterday["close"] + prev_range * self.k

        if current_price >= target_price:
            return "buy", f"돌파 목표가 달성 (현재가={current_price:,} >= 목표={target_price:,.0f})"

        return "hold", f"목표가 미달 (현재가={current_price:,} < 목표={target_price:,.0f})"


# 사용 가능한 전략 목록
AVAILABLE_STRATEGIES = {
    "golden_cross": GoldenCrossStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "volatility_breakout": VolatilityBreakoutStrategy,
}
