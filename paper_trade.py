import json
import os
from datetime import datetime, timezone
from config import INITIAL_CAPITAL, TRADE_SIZE_USDT, STATE_FILE
from exchange import get_ohlcv
import notion_logger


class PaperTrader:
    def __init__(self):
        self._load()

    def _load(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                state = json.load(f)
            self.capital = state['capital']
            self.open_trades = state['open_trades']
            self.closed_trades = state['closed_trades']
        else:
            self.capital = INITIAL_CAPITAL
            self.open_trades = []
            self.closed_trades = []
            self._save()

    def _save(self):
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'capital': self.capital,
                'open_trades': self.open_trades,
                'closed_trades': self.closed_trades,
            }, f, indent=2, default=str)

    def open_trade(self, symbol, signal):
        # 동일 종목 오픈 포지션 중복 방지
        if any(t['symbol'] == symbol for t in self.open_trades):
            return

        trade = {
            'symbol': symbol,
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'size_usdt': TRADE_SIZE_USDT,
            'open_time': datetime.now(timezone.utc).isoformat(),
            'signal_candle_time': str(signal['candle_time']),
        }
        page_id = notion_logger.create_entry(trade)
        if page_id:
            trade['notion_page_id'] = page_id

        self.open_trades.append(trade)
        self._save()

    def update_open_trades(self, exchange):
        """15분봉 마감 시 오픈 포지션 청산 (SL/TP 또는 봉 마감 기준)."""
        if not self.open_trades:
            return

        symbols = list({t['symbol'] for t in self.open_trades})
        to_close = []

        for symbol in symbols:
            try:
                df = get_ohlcv(exchange, symbol, '15m', limit=3)
                # iloc[-1]: 현재 형성 중, iloc[-2]: 방금 마감된 청산 봉
                exit_candle = df.iloc[-2]
            except Exception as e:
                print(f"  [오류] {symbol} 업데이트 실패: {e}")
                continue

            for trade in self.open_trades:
                if trade['symbol'] != symbol:
                    continue

                entry = trade['entry']
                sl = trade['sl']
                tp = trade['tp']
                side = trade['side']

                if side == 'long':
                    if exit_candle['low'] <= sl:
                        exit_price, result = sl, 'SL'
                    elif exit_candle['high'] >= tp:
                        exit_price, result = tp, 'TP'
                    else:
                        exit_price, result = exit_candle['close'], 'CLOSE'
                else:
                    if exit_candle['high'] >= sl:
                        exit_price, result = sl, 'SL'
                    elif exit_candle['low'] <= tp:
                        exit_price, result = tp, 'TP'
                    else:
                        exit_price, result = exit_candle['close'], 'CLOSE'

                if side == 'long':
                    pnl_pct = (exit_price - entry) / entry
                else:
                    pnl_pct = (entry - exit_price) / entry

                pnl_usdt = trade['size_usdt'] * pnl_pct
                self.capital += pnl_usdt

                closed = {
                    **trade,
                    'exit': exit_price,
                    'pnl_usdt': round(pnl_usdt, 2),
                    'pnl_pct': round(pnl_pct * 100, 3),
                    'result': result,
                    'close_time': datetime.now(timezone.utc).isoformat(),
                }
                self.closed_trades.append(closed)
                to_close.append(trade)
                notion_logger.update_exit(closed)

                marker = 'WIN' if pnl_usdt > 0 else 'LOSS'
                print(f"  [{result}/{marker}] {symbol} {side.upper()} "
                      f"| {entry:.4f} → {exit_price:.4f} "
                      f"| PnL: {pnl_usdt:+.2f} USDT ({pnl_pct*100:+.3f}%)")

        self.open_trades = [t for t in self.open_trades if t not in to_close]
        self._save()

    def print_summary(self):
        total = len(self.closed_trades)
        wins = sum(1 for t in self.closed_trades if t['pnl_usdt'] > 0)
        total_pnl = sum(t['pnl_usdt'] for t in self.closed_trades)
        win_rate = (wins / total * 100) if total > 0 else 0.0

        print(f"\n  [요약] 자본: ${self.capital:,.2f} | 거래: {total}회 | "
              f"승률: {win_rate:.1f}% | 누적 PnL: {total_pnl:+.2f} USDT")

        if self.open_trades:
            print(f"  [오픈] {len(self.open_trades)}개 포지션 보유 중")
            for t in self.open_trades:
                print(f"    {t['symbol']} {t['side'].upper()} @ {t['entry']:.4f} "
                      f"| SL: {t['sl']:.4f} | TP: {t['tp']:.4f}")
