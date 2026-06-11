import ccxt
import pandas as pd
from config import TOP_N


def get_exchange():
    return ccxt.binance({'options': {'defaultType': 'future'}})


def get_top_symbols(exchange, n=TOP_N):
    tickers = exchange.fetch_tickers()
    usdt_perps = {
        k: v for k, v in tickers.items()
        if k.endswith('/USDT:USDT') and v.get('quoteVolume')
    }
    sorted_symbols = sorted(
        usdt_perps.items(),
        key=lambda x: x[1]['quoteVolume'],
        reverse=True
    )
    return [s[0] for s in sorted_symbols[:n]]


def get_ohlcv(exchange, symbol, timeframe, limit=250):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df
