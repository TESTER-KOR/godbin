import sys
sys.stdout.reconfigure(encoding='utf-8')

from exchange import get_exchange, get_top_symbols, get_ohlcv
from signals import check_trend, detect_signal
from risk import calc_sl, calc_tp, calc_qty
from config import BTC_SYMBOL, INITIAL_CAPITAL

exchange = get_exchange()

# BTC 추세
df_btc_1h = get_ohlcv(exchange, BTC_SYMBOL, '1h', limit=220)
df_btc_4h = get_ohlcv(exchange, BTC_SYMBOL, '4h', limit=220)
btc_trend = check_trend(df_btc_1h, df_btc_4h)
print(f"BTC 추세: {btc_trend}")
print()

symbols = get_top_symbols(exchange)
print(f"스캔 종목: {', '.join(s.split('/')[0] for s in symbols)}")
print()

for sym in symbols:
    try:
        df_1h = get_ohlcv(exchange, sym, '1h', limit=220)
        df_4h = get_ohlcv(exchange, sym, '4h', limit=220)
        trend = check_trend(df_1h, df_4h)

        if sym != BTC_SYMBOL and trend != btc_trend:
            print(f"{sym:<22} [{trend}] BTC 불일치 — 스킵")
            continue
        if trend == 'NO_TRADE':
            print(f"{sym:<22} NO_TRADE (추세불일치 or ADX미달)")
            continue

        df_15m    = get_ohlcv(exchange, sym, '15m', limit=30)
        confirmed = df_15m.iloc[:-1]
        signal    = detect_signal(confirmed, trend)

        if signal:
            sl = calc_sl(signal)
            if sl:
                tp  = calc_tp(signal['entry'], sl, signal['side'])
                sz, lev = calc_qty(INITIAL_CAPITAL, signal['entry'], sl, signal['side'])
                R = abs(signal['entry'] - sl)
                print(f"{sym:<22} [{trend}] ★{signal['side'].upper()}/{signal['grade']}★ "
                      f"진입:{signal['entry']:.4f} SL:{sl:.4f} TP:{tp:.4f} "
                      f"R={R:.4f} {sz:.0f}U x{lev:.0f}")
            else:
                print(f"{sym:<22} [{trend}] 신호있으나 SL 무효")
        else:
            print(f"{sym:<22} [{trend}] 신호없음")
    except Exception as e:
        print(f"{sym:<22} 오류: {e}")
