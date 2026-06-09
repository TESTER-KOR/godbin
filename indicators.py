import pandas as pd
from config import EMA_LEN, ADX_LEN, ATR_LEN, AVG_BODY_N


def ema(series: pd.Series, period: int = EMA_LEN) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = ATR_LEN) -> pd.Series:
    h, l, c = df['high'], df['low'], df['close']
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = ADX_LEN) -> pd.Series:
    h, l, c = df['high'], df['low'], df['close']
    up   = h.diff()
    down = -l.diff()
    dm_plus  = ((up > down) & (up > 0)).astype(float) * up
    dm_minus = ((down > up) & (down > 0)).astype(float) * down
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr_w    = tr.ewm(alpha=1 / period, adjust=False).mean()
    di_plus  = 100 * dm_plus.ewm(alpha=1 / period, adjust=False).mean() / atr_w
    di_minus = 100 * dm_minus.ewm(alpha=1 / period, adjust=False).mean() / atr_w
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-10)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def avg_body(df: pd.DataFrame, n: int = AVG_BODY_N) -> pd.Series:
    return (df['close'] - df['open']).abs().rolling(n).mean()
