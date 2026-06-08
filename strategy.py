from config import EMA_PERIOD, MIN_BODY_RATIO, MIN_WICK_RATIO, RISK_REWARD


def get_ema(series, period=EMA_PERIOD):
    return series.ewm(span=period, adjust=False).mean()


def check_trend(df_4h, df_1h):
    """1H, 4H 200 EMA 기준 추세 일치 시 'long'/'short', 불일치 시 None."""
    ema_4h = get_ema(df_4h['close']).iloc[-1]
    ema_1h = get_ema(df_1h['close']).iloc[-1]

    trend_4h = 'long' if df_4h['close'].iloc[-1] > ema_4h else 'short'
    trend_1h = 'long' if df_1h['close'].iloc[-1] > ema_1h else 'short'

    return trend_4h if trend_4h == trend_1h else None


def _decent_body(candle):
    """몸통이 전체 범위 대비 MIN_BODY_RATIO 이상인지 확인."""
    rng = candle['high'] - candle['low']
    if rng == 0:
        return False
    body = abs(candle['close'] - candle['open'])
    return (body / rng) >= MIN_BODY_RATIO


def detect_signal(df, trend):
    """
    15분봉 기준 진입 신호 탐지.
    df.iloc[-1]: 현재 형성 중인 봉 (미마감)
    df.iloc[-2]: 직전 마감 봉 (신호 봉)
    df.iloc[-3]: 그 이전 봉 (조건 봉)

    반환: {side, entry, sl, tp, candle_time} 또는 None
    """
    if len(df) < 4:
        return None

    sig = df.iloc[-2]   # 신호 봉 (방금 마감)
    prev = df.iloc[-3]  # 신호 봉 이전 봉

    if trend == 'long':
        # 조건 봉: 적당한 몸통의 음봉
        if not (prev['close'] < prev['open'] and _decent_body(prev)):
            return None
        # 신호 봉: 아래꼬리 그리며 양봉으로 마감
        if sig['close'] <= sig['open']:
            return None
        body = sig['close'] - sig['open']
        lower_wick = sig['open'] - sig['low']
        if lower_wick / body < MIN_WICK_RATIO:
            return None

        entry = sig['close']
        sl = sig['low']
        risk = entry - sl
        if risk <= 0:
            return None
        tp = entry + risk * RISK_REWARD
        return {'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                'candle_time': sig['timestamp']}

    elif trend == 'short':
        # 조건 봉: 적당한 몸통의 양봉
        if not (prev['close'] > prev['open'] and _decent_body(prev)):
            return None
        # 신호 봉: 위꼬리 그리며 음봉으로 마감
        if sig['close'] >= sig['open']:
            return None
        body = sig['open'] - sig['close']
        upper_wick = sig['high'] - sig['open']
        if upper_wick / body < MIN_WICK_RATIO:
            return None

        entry = sig['close']
        sl = sig['high']
        risk = sl - entry
        if risk <= 0:
            return None
        tp = entry - risk * RISK_REWARD
        return {'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                'candle_time': sig['timestamp']}

    return None
