@echo off
cd /d %~dp0
python -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
from exchange import get_exchange, get_top_symbols, get_ohlcv
from strategy import check_trend, detect_signal
exchange = get_exchange()
for sym in get_top_symbols(exchange):
    df4 = get_ohlcv(exchange, sym, '4h', 210)
    df1 = get_ohlcv(exchange, sym, '1h', 210)
    trend = check_trend(df4, df1)
    if not trend: continue
    df15 = get_ohlcv(exchange, sym, '15m', 5)
    sig = detect_signal(df15, trend)
    print(sym, trend, sig if sig else '신호없음')
"
pause
