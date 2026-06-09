import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from exchange import get_exchange, get_top_symbols, get_ohlcv
from signals import check_trend, detect_signal
from paper_trade import PaperTrader
from config import BTC_SYMBOL


def main():
    exchange = get_exchange()
    trader   = PaperTrader()
    last_boundary = -1

    print("=" * 60)
    print("갓빈 매매법 페이퍼 트레이딩 v2")
    print(f"초기 자본: ${trader.capital:,.2f} USDT")
    print("15분봉 마감 시마다 자동 스캔 (UTC :00 :15 :30 :45)")
    print("=" * 60)

    while True:
        now      = datetime.now(timezone.utc)
        boundary = (now.hour * 60 + now.minute) // 15

        if now.minute % 15 == 0 and now.second < 30 and boundary != last_boundary:
            last_boundary = boundary
            ts = now.strftime('%Y-%m-%d %H:%M UTC')
            print(f"\n{'='*60}\n[{ts}]")

            # 1. 오픈 포지션 청산 체크
            if trader.open_trades:
                print("▶ 포지션 업데이트")
                trader.update_open_trades(exchange)

            # 2. 안전장치 확인
            if not trader.is_trading_allowed():
                trader.print_summary()
                time.sleep(10)
                continue

            # 3. BTC 추세 (알트 정렬 기준)
            try:
                df_btc_1h = get_ohlcv(exchange, BTC_SYMBOL, '1h', limit=220)
                df_btc_4h = get_ohlcv(exchange, BTC_SYMBOL, '4h', limit=220)
                btc_trend = check_trend(df_btc_1h, df_btc_4h)
                print(f"▶ BTC 추세: {btc_trend}")
            except Exception as e:
                print(f"  BTC 추세 조회 실패: {e}")
                time.sleep(10)
                continue

            if btc_trend == 'NO_TRADE':
                print("  BTC 추세 불명확 — 스캔 스킵")
                trader.print_summary()
                time.sleep(10)
                continue

            # 4. 종목 스캔
            print("▶ 종목 스캔 중...")
            try:
                symbols = get_top_symbols(exchange)
                print(f"  대상: {', '.join(s.split('/')[0] for s in symbols)}")
            except Exception as e:
                print(f"  종목 조회 실패: {e}")
                time.sleep(10)
                continue

            found = 0
            for symbol in symbols:
                if not trader.can_open(symbol):
                    continue
                try:
                    df_1h = get_ohlcv(exchange, symbol, '1h', limit=220)
                    df_4h = get_ohlcv(exchange, symbol, '4h', limit=220)
                    trend = check_trend(df_1h, df_4h)

                    # BTC와 추세 방향 일치 확인 (BTC 자체는 제외)
                    if symbol != BTC_SYMBOL and trend != btc_trend:
                        continue
                    if trend == 'NO_TRADE':
                        continue

                    df_15m        = get_ohlcv(exchange, symbol, '15m', limit=30)
                    confirmed_15m = df_15m.iloc[:-1]  # 형성 중인 봉 제외
                    signal        = detect_signal(confirmed_15m, trend)

                    if signal:
                        found += 1
                        print(f"  [신호/{signal['grade']}] {symbol} {signal['side'].upper()} "
                              f"진입:{signal['entry']:.4f}")
                        trader.open_trade(symbol, signal)
                        break  # 동시 1포지션

                except Exception as e:
                    print(f"  [{symbol}] 오류: {e}")

            if found == 0:
                print("  신호 없음")

            trader.print_summary()

        time.sleep(10)


if __name__ == '__main__':
    main()
