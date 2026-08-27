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

        # --- Trend persistence signals ---

    def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
        """Linear-regression slope of `series` over a rolling window."""
        return series.rolling(window).apply(
            lambda values: np.polyfit(
                np.arange(len(values)),
                values,
                1,
            )[0],
            raw=True,
        )

    # Normalized (%-per-day) slope of price itself: a real trend-strength
    # number rather than a boolean "is Close above SMA_20 today" check.
    close_slope_10d = _rolling_slope(close, 10)
    df["CLOSE_SLOPE_10D"] = (close_slope_10d / close) * 100

    # Is the moving average itself rising, not just "is price above it"?
    sma20_slope = _rolling_slope(df["SMA_20"], 5)
    df["SMA_20_SLOPE"] = (sma20_slope / df["SMA_20"]) * 100

    # Consistency: fraction of the last 10 sessions that closed up.
    up_day = (df["RETURN_1D"] > 0).astype(float)
    df["UP_DAY_RATIO_10D"] = up_day.rolling(10).mean()

    # How established is the trend — consecutive days above SMA_50,
    # reset to 0 whenever price drops below it.
    above_sma50 = (close > df["SMA_50"]).astype(int)
    run_id = (above_sma50 != above_sma50.shift()).cumsum()
    days_above = above_sma50.groupby(run_id).cumcount() + 1
    df["DAYS_ABOVE_SMA_50"] = days_above.where(above_sma50 == 1, 0)

    return df