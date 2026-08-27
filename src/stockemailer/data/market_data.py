from typing import Optional

import pandas as pd
import yfinance as yf


def get_stock_history(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """
    Download historical OHLCV data for a stock.

    Example ticker:
        RELIANCE.NS
        TCS.NS
        HDFCBANK.NS
    """

    try:
        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

        if data.empty:
            return None

        # yfinance can return MultiIndex columns.
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.dropna()

        return data

    except Exception as exc:
        print(f"Error downloading {ticker}: {exc}")
        return None


def get_stock_history_between(
    ticker: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """Download OHLCV data for an inclusive backtest date window.

    Yahoo Finance treats ``end`` as exclusive, so callers should provide an
    end date after the final trading day they need. Intraday intervals such as
    ``15m`` are limited to recent historical windows by Yahoo Finance.
    """

    try:
        data = yf.download(
            ticker,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

        if data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        return data.dropna()

    except Exception as exc:
        print(f"Error downloading {ticker}: {exc}")
        return None