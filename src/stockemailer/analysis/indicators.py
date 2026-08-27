import numpy as np
import pandas as pd
from ta.momentum import ROCIndicator, StochasticOscillator, WilliamsRIndicator
from ta.trend import ADXIndicator, CCIIndicator
from ta.volume import OnBalanceVolumeIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators on OHLCV data.
    """

    df = df.copy()

    close = df["Close"]
    volume = df["Volume"]

    # Moving averages
    df["SMA_20"] = SMAIndicator(
        close=close,
        window=20
    ).sma_indicator()

    df["SMA_50"] = SMAIndicator(
        close=close,
        window=50
    ).sma_indicator()

    df["SMA_200"] = SMAIndicator(
        close=close,
        window=200
    ).sma_indicator()

    # RSI
    df["RSI"] = RSIIndicator(
        close=close,
        window=14
    ).rsi()

    # MACD
    macd = MACD(close=close)

    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()
    df["MACD_HIST"] = macd.macd_diff()

    # Returns
    df["RETURN_1D"] = close.pct_change(1) * 100
    df["RETURN_2D"] = close.pct_change(2) * 100
    df["RETURN_5D"] = close.pct_change(5) * 100

    # Volume
    df["AVG_VOLUME_20"] = volume.rolling(20).mean()

    df["VOLUME_RATIO"] = (
        volume / df["AVG_VOLUME_20"]
    )

    return df


def calculate_extended_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the legacy and extended technical indicators.

    ``VWAP_20`` is a rolling daily-bar approximation: it uses each day's
    closing price and volume because true intraday VWAP data is unavailable.
    It should not be interpreted as a session VWAP.
    """

    df = calculate_indicators(df)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    atr = AverageTrueRange(
        high=high,
        low=low,
        close=close,
        window=14,
    )
    df["ATR_14"] = atr.average_true_range()

    bollinger = BollingerBands(
        close=close,
        window=20,
        window_dev=2,
    )
    df["BOLL_UPPER"] = bollinger.bollinger_hband()
    df["BOLL_MIDDLE"] = bollinger.bollinger_mavg()
    df["BOLL_LOWER"] = bollinger.bollinger_lband()
    df["BOLL_WIDTH"] = (
        (df["BOLL_UPPER"] - df["BOLL_LOWER"])
        / df["BOLL_MIDDLE"]
        * 100
    )

    adx = ADXIndicator(
        high=high,
        low=low,
        close=close,
        window=14,
    )
    df["ADX_14"] = adx.adx()
    df["PLUS_DI"] = adx.adx_pos()
    df["MINUS_DI"] = adx.adx_neg()

    stochastic = StochasticOscillator(
        high=high,
        low=low,
        close=close,
        window=14,
        smooth_window=3,
    )
    df["STOCH_K"] = stochastic.stoch()
    df["STOCH_D"] = stochastic.stoch_signal()
    df["CCI_20"] = CCIIndicator(
        high=high,
        low=low,
        close=close,
        window=20,
    ).cci()
    df["WILLIAMS_R"] = WilliamsRIndicator(
        high=high,
        low=low,
        close=close,
        lbp=14,
    ).williams_r()

    df["OBV"] = OnBalanceVolumeIndicator(
        close=close,
        volume=volume,
    ).on_balance_volume()
    obv_mean = df["OBV"].rolling(5).mean().abs()
    obv_slope = df["OBV"].rolling(5).apply(
        lambda values: np.polyfit(
            np.arange(len(values)),
            values,
            1,
        )[0],
        raw=True,
    )
    df["OBV_SLOPE_5"] = obv_slope / obv_mean.replace(0, np.nan)
    df["VWAP_20"] = (
        (close * volume).rolling(20).sum()
        / volume.rolling(20).sum()
    )
    df["ROC_10"] = ROCIndicator(
        close=close,
        window=10,
    ).roc()

    return df