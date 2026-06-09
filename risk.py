from config import CONFIRM_BODY_MULT, RR_RATIO, RISK_PER_TRADE, LEVERAGE_CAP


def calc_sl(signal: dict) -> float | None:
    """
    §5: 손절선 = 직전봉 중간값. 직전봉이 너무 작으면 신호봉 저/고점으로 폴백.
    안전장치: SL이 진입가 반대편이거나 0.1% 미만이면 폴백 후 재검증.
    Returns SL price or None (진입 취소).
    """
    side      = signal['side']
    entry     = signal['entry']
    prev_mid  = (signal['prev_high'] + signal['prev_low']) / 2
    prev_body = signal['prev_body']
    avg_b     = signal['avg_body']

    if side == 'long':
        sl = prev_mid if prev_body >= avg_b * CONFIRM_BODY_MULT else signal['sig_low']
        # 안전장치
        if sl >= entry or (entry - sl) / entry < 0.001:
            sl = signal['sig_low']
        if sl >= entry:
            return None
    else:
        sl = prev_mid if prev_body >= avg_b * CONFIRM_BODY_MULT else signal['sig_high']
        if sl <= entry or (sl - entry) / entry < 0.001:
            sl = signal['sig_high']
        if sl <= entry:
            return None

    return sl


def calc_tp(entry: float, sl: float, side: str) -> float:
    R = abs(entry - sl)
    return entry + R * RR_RATIO if side == 'long' else entry - R * RR_RATIO


def calc_qty(capital: float, entry: float, sl: float, side: str) -> tuple[float, float]:
    """
    RISK_PCT: SL 도달 시 손실 = capital * RISK_PER_TRADE.
    Returns (size_usdt, implied_leverage). LEVERAGE_CAP 초과 시 사이즈 축소.
    """
    R = abs(entry - sl)
    if R <= 0:
        return 0.0, 0.0

    risk_usdt = capital * RISK_PER_TRADE
    qty_base  = risk_usdt / R
    notional  = qty_base * entry
    leverage  = notional / capital

    if leverage > LEVERAGE_CAP:
        notional = capital * LEVERAGE_CAP
        leverage = LEVERAGE_CAP

    return notional, leverage
