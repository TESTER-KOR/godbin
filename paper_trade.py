import json
import os
from datetime import datetime, timezone, date

from config import (
    INITIAL_CAPITAL, STATE_FILE, EXIT_MODE, PROFIT_HOLD_PCT,
    MAX_DAILY_LOSS_PCT, N_CONSEC_SL, COOLDOWN_LONG_SEC, MAX_POSITIONS,
)
from exchange import get_ohlcv
from risk import calc_sl, calc_tp, calc_qty
import notion_logger


class PaperTrader:
    def __init__(self):
        self._load()

    def _load(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                s = json.load(f)
            self.capital        = s['capital']
            self.open_trades    = s['open_trades']
            self.closed_trades  = s['closed_trades']
            self.daily_pnl      = s.get('daily_pnl', 0.0)
            self.last_date      = s.get('last_date', str(date.today()))
            self.consec_sl      = s.get('consec_sl', 0)
            self.cooldown_until = s.get('cooldown_until', None)
        else:
            self.capital        = INITIAL_CAPITAL
            self.open_trades    = []
            self.closed_trades  = []
            self.daily_pnl      = 0.0
            self.last_date      = str(date.today())
            self.consec_sl      = 0
            self.cooldown_until = None
            self._save()

    def _save(self):
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'capital':        self.capital,
                'open_trades':    self.open_trades,
                'closed_trades':  self.closed_trades,
                'daily_pnl':      self.daily_pnl,
                'last_date':      self.last_date,
                'consec_sl':      self.consec_sl,
                'cooldown_until': self.cooldown_until,
            }, f, indent=2, default=str)

    def _reset_daily_if_needed(self):
        today = str(date.today())
        if self.last_date != today:
            self.daily_pnl = 0.0
            self.last_date = today

    def is_trading_allowed(self) -> bool:
        self._reset_daily_if_needed()
        if -self.daily_pnl >= self.capital * MAX_DAILY_LOSS_PCT:
            print(f"  [킬스위치] 일일 손실 한도 도달 ({-self.daily_pnl:.2f} USDT) — 오늘 신규 진입 중단")
            return False
        if self.cooldown_until:
            until = datetime.fromisoformat(self.cooldown_until)
            if datetime.now(timezone.utc) < until:
                remaining = int((until - datetime.now(timezone.utc)).total_seconds() // 60)
                print(f"  [쿨다운] {remaining}분 남음 (연속 {self.consec_sl}회 손절)")
                return False
            self.cooldown_until = None
        return True

    def can_open(self, symbol: str) -> bool:
        if len(self.open_trades) >= MAX_POSITIONS:
            return False
        if any(t['symbol'] == symbol for t in self.open_trades):
            return False
        return True

    def open_trade(self, symbol: str, signal: dict):
        if not self.can_open(symbol):
            return

        sl = calc_sl(signal)
        if sl is None:
            print(f"  [{symbol}] SL 계산 무효 — 진입 취소")
            return

        entry              = signal['entry']
        side               = signal['side']
        tp                 = calc_tp(entry, sl, side)
        size_usdt, lev     = calc_qty(self.capital, entry, sl, side)

        if size_usdt <= 0:
            print(f"  [{symbol}] 포지션 사이즈 오류 — 진입 취소")
            return

        R = abs(entry - sl)
        trade = {
            'symbol':      symbol,
            'side':        side,
            'entry':       entry,
            'sl':          sl,
            'tp':          tp,
            'size_usdt':   size_usdt,
            'leverage':    round(lev, 1),
            'grade':       signal['grade'],
            'open_time':   datetime.now(timezone.utc).isoformat(),
            'candle_time': signal['candle_time'],
            'hold_bars':   0,
        }

        page_id = notion_logger.create_entry(trade)
        if page_id:
            trade['notion_page_id'] = page_id

        self.open_trades.append(trade)
        self._save()

        print(f"  [진입/{signal['grade']}] {symbol} {side.upper()} "
              f"@ {entry:.4f}  SL:{sl:.4f}  TP:{tp:.4f} "
              f"| R={R:.4f}  {size_usdt:.0f}USDT x{lev:.0f}")

    def update_open_trades(self, exchange) -> int:
        if not self.open_trades:
            return 0

        to_close  = []
        to_update = []

        for trade in list(self.open_trades):
            symbol = trade['symbol']
            try:
                df        = get_ohlcv(exchange, symbol, '15m', limit=5)
                exit_c    = df.iloc[-2]  # 방금 마감된 봉
            except Exception as e:
                print(f"  [{symbol}] 데이터 오류: {e}")
                continue

            entry  = trade['entry']
            sl     = trade['sl']
            tp     = trade['tp']
            side   = trade['side']
            size_u = trade['size_usdt']

            exit_price    = None
            closed_result = None

            if EXIT_MODE == 'CANDLE_ONLY':
                exit_price, closed_result = exit_c['close'], 'CLOSE'

            elif EXIT_MODE == 'RR_ONLY':
                if side == 'long':
                    if exit_c['low'] <= sl:
                        exit_price, closed_result = sl, 'SL'
                    elif exit_c['high'] >= tp:
                        exit_price, closed_result = tp, 'TP'
                else:
                    if exit_c['high'] >= sl:
                        exit_price, closed_result = sl, 'SL'
                    elif exit_c['low'] <= tp:
                        exit_price, closed_result = tp, 'TP'

            else:  # HYBRID
                if side == 'long':
                    if exit_c['low'] <= sl:
                        exit_price, closed_result = sl, 'SL'
                    elif exit_c['high'] >= tp:
                        exit_price, closed_result = tp, 'TP'
                    else:
                        unrealized = (exit_c['close'] - entry) / entry
                        if unrealized >= PROFIT_HOLD_PCT:
                            trade['sl']        = max(sl, entry)  # SL → 본전 이상
                            trade['hold_bars'] = trade.get('hold_bars', 0) + 1
                            print(f"  [보유연장] {symbol} 미실현 {unrealized*100:+.1f}% "
                                  f"→ 다음 봉 대기 (SL → {trade['sl']:.4f})")
                            to_update.append(trade)
                            continue
                        else:
                            exit_price, closed_result = exit_c['close'], 'CLOSE'
                else:
                    if exit_c['high'] >= sl:
                        exit_price, closed_result = sl, 'SL'
                    elif exit_c['low'] <= tp:
                        exit_price, closed_result = tp, 'TP'
                    else:
                        unrealized = (entry - exit_c['close']) / entry
                        if unrealized >= PROFIT_HOLD_PCT:
                            trade['sl']        = min(sl, entry)
                            trade['hold_bars'] = trade.get('hold_bars', 0) + 1
                            print(f"  [보유연장] {symbol} 미실현 {unrealized*100:+.1f}% "
                                  f"→ 다음 봉 대기 (SL → {trade['sl']:.4f})")
                            to_update.append(trade)
                            continue
                        else:
                            exit_price, closed_result = exit_c['close'], 'CLOSE'

            if closed_result is None:
                continue

            pnl_pct  = (exit_price - entry) / entry if side == 'long' else (entry - exit_price) / entry
            pnl_usdt = size_u * pnl_pct
            self.capital   += pnl_usdt
            self.daily_pnl += pnl_usdt

            if closed_result == 'SL':
                self.consec_sl += 1
                if self.consec_sl >= N_CONSEC_SL:
                    from datetime import timedelta
                    until = datetime.now(timezone.utc) + timedelta(seconds=COOLDOWN_LONG_SEC)
                    self.cooldown_until = until.isoformat()
                    print(f"  [쿨다운 시작] 연속 {self.consec_sl}회 손절 → 1시간 휴식")
            else:
                self.consec_sl = 0

            closed = {
                **trade,
                'exit':       exit_price,
                'pnl_usdt':   round(pnl_usdt, 2),
                'pnl_pct':    round(pnl_pct * 100, 3),
                'result':     closed_result,
                'close_time': datetime.now(timezone.utc).isoformat(),
            }
            self.closed_trades.append(closed)
            to_close.append(trade)
            notion_logger.update_exit(closed)

            marker = 'WIN' if pnl_usdt > 0 else 'LOSS'
            print(f"  [{closed_result}/{marker}] {symbol} {side.upper()} "
                  f"| {entry:.4f} → {exit_price:.4f} "
                  f"| PnL: {pnl_usdt:+.2f}U ({pnl_pct*100:+.3f}%)")

        self.open_trades = [t for t in self.open_trades if t not in to_close]
        self._save()
        return len(to_close)

    def print_summary(self):
        total     = len(self.closed_trades)
        wins      = sum(1 for t in self.closed_trades if t['pnl_usdt'] > 0)
        total_pnl = sum(t['pnl_usdt'] for t in self.closed_trades)
        wr        = (wins / total * 100) if total else 0.0

        print(f"\n  [요약] 자본: ${self.capital:,.2f} | 거래: {total}회 | "
              f"승률: {wr:.1f}% | 누적PnL: {total_pnl:+.2f}U | "
              f"오늘PnL: {self.daily_pnl:+.2f}U | 연속손절: {self.consec_sl}")

        for t in self.open_trades:
            bars = t.get('hold_bars', 0)
            print(f"  [오픈/{t['grade']}] {t['symbol']} {t['side'].upper()} "
                  f"@ {t['entry']:.4f} | SL:{t['sl']:.4f} TP:{t['tp']:.4f} "
                  f"| {t['size_usdt']:.0f}U x{t['leverage']} ({bars}봉 보유)")
