import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from exchange import get_exchange, get_top_symbols, get_ohlcv
from strategy import check_trend, detect_signal
from paper_trade import PaperTrader


def main():
    exchange = get_exchange()
    trader = PaperTrader()
    last_boundary = -1

    print("=" * 60)
    print("갓빈 매매법 페이퍼 트레이딩")
    print(f"초기 자본: ${trader.capital:,.2f} USDT")
    print("15분봉 마감 시마다 자동 스캔 (UTC 기준 :00 :15 :30 :45)")
    print("=" * 60)

    while True:
        now = datetime.now(timezone.utc)
        boundary = (now.hour * 60 + now.minute) // 15

        if now.minute % 15 == 0 and now.second < 30 and boundary != last_boundary:
            last_boundary = boundary
            ts = now.strftime('%Y-%m-%d %H:%M UTC')
            print(f"\n{'='*60}")
            print(f"[{ts}]")

            # 1. 오픈 포지션 청산 체크 (직전 봉 기준)
            if trader.open_trades:
                print("▶ 포지션 업데이트")
                trader.update_open_trades(exchange)

            # 2. 새 신호 탐색
            print("▶ 신호 탐색 중...")
            try:
                symbols = get_top_symbols(exchange)
                labels = ', '.join(s.split('/')[0] for s in symbols)
                print(f"  종목: {labels}")
            except Exception as e:
                print(f"  종목 조회 실패: {e}")
                time.sleep(10)
                continue

            found = 0
            for symbol in symbols:
                try:
                    df_4h = get_ohlcv(exchange, symbol, '4h', limit=210)
                    df_1h = get_ohlcv(exchange, symbol, '1h', limit=210)
                    trend = check_trend(df_4h, df_1h)
                    if trend is None:
                        continue

                    df_15m = get_ohlcv(exchange, symbol, '15m', limit=5)
                    signal = detect_signal(df_15m, trend)
                    if signal:
                        found += 1
                        trader.open_trade(symbol, signal)
                        print(f"  [신호] {symbol} {signal['side'].upper()} "
                              f"| 진입: {signal['entry']:.4f} "
                              f"| SL: {signal['sl']:.4f} "
                              f"| TP: {signal['tp']:.4f} "
                              f"| 추세: {trend}")
                except Exception as e:
                    print(f"  [{symbol}] 오류: {e}")

            if found == 0:
                print("  신호 없음")

            trader.print_summary()

        time.sleep(10)


if __name__ == '__main__':
    main()
