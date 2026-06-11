import sys
sys.stdout.reconfigure(encoding='utf-8')

from exchange import get_exchange, get_top_symbols, get_ohlcv
from signals import check_trend, detect_signal
from paper_trade import PaperTrader
from config import BTC_SYMBOL

exchange = get_exchange()
trader   = PaperTrader()

# 1. 오픈 포지션 청산 체크
closed_count = 0
if trader.open_trades:
    print("▶ 포지션 업데이트")
    closed_count = trader.update_open_trades(exchange)

if closed_count > 0:
    print("  청산 발생 — 이번 봉 신규 진입 스킵")
    trader.print_summary()
    sys.exit(0)

# 2. 안전장치 확인
if not trader.is_trading_allowed():
    trader.print_summary()
    sys.exit(0)

# 3. BTC 추세
df_btc_1h = get_ohlcv(exchange, BTC_SYMBOL, '1h', limit=220)
df_btc_4h = get_ohlcv(exchange, BTC_SYMBOL, '4h', limit=220)
btc_trend = check_trend(df_btc_1h, df_btc_4h)
print(f"▶ BTC 추세: {btc_trend}")

if btc_trend == 'NO_TRADE':
    print("  BTC 추세 불명확 — 스캔 스킵")
    trader.print_summary()
    sys.exit(0)

# 4. 종목 스캔
print("▶ 종목 스캔 중...")
symbols = get_top_symbols(exchange)
print(f"  대상: {', '.join(s.split('/')[0] for s in symbols)}")

for symbol in symbols:
    if not trader.can_open(symbol):
        continue
    try:
        df_1h = get_ohlcv(exchange, symbol, '1h', limit=220)
        df_4h = get_ohlcv(exchange, symbol, '4h', limit=220)
        trend = check_trend(df_1h, df_4h)

        if symbol != BTC_SYMBOL and trend != btc_trend:
            continue
        if trend == 'NO_TRADE':
            continue

        df_15m        = get_ohlcv(exchange, symbol, '15m', limit=30)
        confirmed_15m = df_15m.iloc[:-1]
        signal        = detect_signal(confirmed_15m, trend)

        if signal:
            print(f"  [신호/{signal['grade']}] {symbol} {signal['side'].upper()} 진입:{signal['entry']:.4f}")
            trader.open_trade(symbol, signal)
            break

    except Exception as e:
        print(f"  [{symbol}] 오류: {e}")

trader.print_summary()
