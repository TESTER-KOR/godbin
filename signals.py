import pandas as pd
from config import (
    ADX_MIN, DOJI_RATIO,
    WICK_RANGE_MIN, WICK_BODY_MIN,
    IMPULSE_BODY_MULT, AVG_BODY_N,
)
from indicators import ema, adx, avg_body


def check_trend(df_1h: pd.DataFrame, df_4h: pd.DataFrame) -> str:
    """
    EMA200 1h/4h 방향 일치 + ADX >= ADX_MIN.
    Returns 'UP', 'DOWN', 'NO_TRADE'.
    """
    ema_1h   = ema(df_1h['close']).iloc[-1]
    ema_4h   = ema(df_4h['close']).iloc[-1]
    close_1h = df_1h['close'].iloc[-1]
    close_4h = df_4h['close'].iloc[-1]

    trend_1h = 'UP' if close_1h > ema_1h else 'DOWN'
    trend_4h = 'UP' if close_4h > ema_4h else 'DOWN'

    if trend_1h != trend_4h:
        return 'NO_TRADE'

    if adx(df_1h).iloc[-1] < ADX_MIN:
        return 'NO_TRADE'

    return trend_1h


def detect_signal(df_15m: pd.DataFrame, trend: str) -> dict | None:
    """
    df_15m: 확정 봉만 전달 (형성 중인 마지막 봉 제외).
    iloc[-1] = 신호봉, iloc[-2] = 직전봉.
    최소 AVG_BODY_N + 2 봉 필요.
    """
    if trend == 'NO_TRADE':
        return None
    if len(df_15m) < AVG_BODY_N + 2:
        return None

    sig  = df_15m.iloc[-1]
    prev = df_15m.iloc[-2]

    rng = sig['high'] - sig['low']
    if rng == 0:
        return None
    body = abs(sig['close'] - sig['open'])
    # 도지 제외
    if body / rng <= DOJI_RATIO:
        return None

    lower_wick = min(sig['open'], sig['close']) - sig['low']
    upper_wick = sig['high'] - max(sig['open'], sig['close'])
    avg_b      = avg_body(df_15m).iloc[-2]  # 직전봉 시점의 평균 몸통
    prev_body  = abs(prev['close'] - prev['open'])

    if trend == 'UP':
        # 양전: 양봉 + 직전봉보다 높은 종가
        if not (sig['close'] > sig['open'] and sig['close'] > prev['close']):
            return None
        # 되돌림 꼬리
        if lower_wick / rng < WICK_RANGE_MIN:
            return None
        if lower_wick < body * WICK_BODY_MIN:
            return None
        # 직전봉이 추세 역행 장대 음봉이면 등급 A
        grade = 'A' if (prev['close'] < prev['open'] and prev_body >= avg_b * IMPULSE_BODY_MULT) else 'B'
        side  = 'long'

    elif trend == 'DOWN':
        # 음전: 음봉 + 직전봉보다 낮은 종가
        if not (sig['close'] < sig['open'] and sig['close'] < prev['close']):
            return None
        # 되돌림 꼬리 (위)
        if upper_wick / rng < WICK_RANGE_MIN:
            return None
        if upper_wick < body * WICK_BODY_MIN:
            return None
        grade = 'A' if (prev['close'] > prev['open'] and prev_body >= avg_b * IMPULSE_BODY_MULT) else 'B'
        side  = 'short'

    else:
        return None

    return {
        'side':        side,
        'entry':       sig['close'],
        'sig_low':     sig['low'],
        'sig_high':    sig['high'],
        'prev_high':   prev['high'],
        'prev_low':    prev['low'],
        'prev_body':   prev_body,
        'avg_body':    avg_b,
        'grade':       grade,
        'candle_time': str(sig['timestamp']),
    }
